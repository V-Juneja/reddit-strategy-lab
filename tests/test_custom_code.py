"""OS boundary tests and engine tests using only cached real observations."""

import json
import platform
from pathlib import Path

import pytest
from pydantic import ValidationError

from reddit_strategy_lab.code_engine import CodeConfig, MarketCommand, load_code_data, simulate_code
from reddit_strategy_lab.code_runner import CodeRunner, RunnerError, verify_sandbox

ROOT = Path(__file__).resolve().parents[1]
MAC = pytest.mark.skipif(platform.system() != "Darwin", reason="macOS Seatbelt runner required")


@pytest.fixture
def config():
    return CodeConfig(universe=["SPY"], timeframe="1d")


@pytest.fixture
def real_data(config):
    path = ROOT / "data/market/SPY-2020-2024.csv"
    if not path.exists():
        pytest.skip("real SPY cache required; no synthetic replacement")
    data, _ = load_code_data(path, config)
    return {s: rows[:12] for s, rows in data.items()}


def algorithm(body):
    return "class Strategy:\n def __init__(self, parameters): pass\n def on_event(self,e,p):\n" + "\n".join(
        "  " + line for line in body.splitlines()
    )


@MAC
def test_os_boundary():
    assert verify_sandbox()["network"] == "denied"


@MAC
def test_deadline_kills_worker():
    with CodeRunner(algorithm("while True: pass"), {}, timeout=0.3) as worker:
        with pytest.raises(RunnerError, match="deadline"):
            worker.step({"sequence": 0}, {})
    assert worker.process.poll() is not None


@MAC
def test_protocol_output_limit():
    with CodeRunner(algorithm("return ['x' * 100000]"), {}) as worker:
        with pytest.raises(RunnerError, match="size limit"):
            worker.step({"sequence": 0}, {})


@MAC
def test_parent_files_and_future_data_not_readable(tmp_path):
    future = tmp_path / "future.json"
    future.write_text("not market data: a boundary sentinel")
    source = algorithm(f"return [open({str(future)!r}).read()]")
    with CodeRunner(source, {}) as worker:
        with pytest.raises(RunnerError, match="failed inside"):
            worker.step({"sequence": 0}, {})


@pytest.mark.parametrize(
    "changes",
    [
        dict(quantity=True),
        dict(quantity=1.5),
        dict(quantity=-1),
        dict(type="stop"),
        dict(fill_price=1),
        dict(time="yesterday"),
        dict(quantity=float("nan")),
    ],
)
def test_invalid_commands(changes):
    with pytest.raises(ValidationError):
        MarketCommand.model_validate(dict(id="one", symbol="SPY", side="buy", quantity=1) | changes)


@MAC
def test_real_next_open_and_host_accounting(config, real_data):
    source = algorithm(
        "if e['sequence'] == 0: return [dict(id='b',symbol='SPY',side='buy',quantity=2)]\n"
        "if e['sequence'] == 2: return [dict(id='s',symbol='SPY',side='sell',quantity=2)]\n"
        "return []"
    )
    result = simulate_code(source, config, real_data)
    buy, sell = result["orders"]
    rows = real_data["SPY"]
    assert buy["time"] == rows[1]["start"].isoformat()
    assert sell["time"] == rows[3]["start"].isoformat()
    assert buy["price"] == pytest.approx(rows[1]["open"] * 1.0003)
    assert sell["price"] == pytest.approx(rows[3]["open"] * 0.9997)
    expected = config.capital - 2 * buy["price"] - buy["fee"] + 2 * sell["price"] - sell["fee"]
    assert result["metrics"]["final_equity"] == pytest.approx(expected)
    assert result["metrics"]["open_positions"] == {"SPY": 0}


@MAC
def test_risk_caps_shorting_and_expiry(config, real_data):
    source = algorithm(
        "if e['sequence'] == 0: return [dict(id='s',symbol='SPY',side='sell',quantity=1),"
        "dict(id='b',symbol='SPY',side='buy',quantity=1000000)]\n"
        "return [dict(id='x'+str(e['sequence']),symbol='SPY',side='buy',quantity=1,valid_for='same_session')]"
    )
    result = simulate_code(source, config, real_data)
    assert [o["reason"] for o in result["orders"][:2]] == ["shorting_forbidden", "insufficient_cash"]
    assert result["metrics"]["fills"] == 0
    assert result["orders"][-1]["reason"] == "end_of_data"
    capped = config.model_copy(update={"max_position_fraction": 0.01})
    source = algorithm("return [dict(id=str(e['sequence']),symbol='SPY',side='buy',quantity=1)]")
    assert simulate_code(source, capped, real_data)["orders"][0]["reason"] == "position_cap"


@MAC
def test_prefix_and_deterministic_replay(config, real_data):
    source = algorithm(
        "if e['sequence'] % 3 == 0 and not p['positions']['SPY']: "
        "return [dict(id=str(e['sequence']),symbol='SPY',side='buy',quantity=1)]\n"
        "if p['positions']['SPY'] and e['bars']['SPY']['close'] > e['bars']['SPY']['open']: "
        "return [dict(id=str(e['sequence']),symbol='SPY',side='sell',quantity=1)]\nreturn []"
    )
    full = simulate_code(source, config, real_data)
    repeat = simulate_code(source, config, real_data)
    prefix = simulate_code(source, config, {s: rows[:6] for s, rows in real_data.items()})
    assert full == repeat
    assert full["decisions"][:6] == prefix["decisions"]


@MAC
@pytest.mark.parametrize(
    "body,match",
    [
        ("return [dict(id='same',symbol='SPY',side='buy',quantity=1)]", "duplicate"),
        ("return [dict(id='x',symbol='QQQ',side='buy',quantity=1)]", "unconfigured"),
        ("return {'cash':999999}", "at most"),
    ],
)
def test_worker_cannot_rewrite_engine_state(config, real_data, body, match):
    with pytest.raises(ValueError, match=match):
        simulate_code(algorithm(body), config, real_data)


@MAC
def test_warmup_orders_fail(config, real_data):
    config = config.model_copy(update={"warmup_bars": 3})
    with pytest.raises(ValueError, match="warmup"):
        simulate_code(
            algorithm("return [dict(id='x',symbol='SPY',side='buy',quantity=1)]"), config, real_data
        )


@MAC
def test_custom_state_and_basket():
    config = CodeConfig.model_validate_json((ROOT / "examples/custom-code/config.json").read_text())
    directory = ROOT / "data/basket-verification"
    if not directory.exists():
        pytest.skip("real basket observations required")
    data, _ = load_code_data(directory, config)
    source = (ROOT / "examples/custom-code/cross_sectional.py").read_text()
    result = simulate_code(source, config, {s: rows[:70] for s, rows in data.items()})
    assert result["metrics"]["fills"] > 0
    assert all(point["cash"] >= 0 for point in result["curve"])
    assert all(o["symbol"] in config.universe for o in result["orders"])


@MAC
def test_run_artifacts_and_failure_registry(config, tmp_path):
    from reddit_strategy_lab.code_experiment import run_code_file

    prices = ROOT / "data/market/SPY-2020-2024.csv"
    if not prices.exists():
        pytest.skip("real market cache required")
    source = tmp_path / "strategy.py"
    source.write_text(algorithm("return []"))
    conf = tmp_path / "config.json"
    conf.write_text(config.model_dump_json())
    folder, metrics = run_code_file(source, conf, prices, tmp_path / "runs")
    assert metrics["final_equity"] == config.capital
    assert json.loads((folder / "result.json").read_text())["audit"]["prefix_match"]
    source.write_text(algorithm("raise RuntimeError('deliberate failure')"))
    with pytest.raises(RunnerError):
        run_code_file(source, conf, prices, tmp_path / "runs")
    records = [json.loads(line) for line in (tmp_path / "runs/trials.jsonl").read_text().splitlines()]
    assert [r["status"] for r in records] == ["started", "completed", "started", "failed"]


@MAC
def test_known_exchange_calendar_exposes_holiday_without_future_prices():
    prices = ROOT / "data/market/SPY-2020-2024.csv"
    if not prices.exists():
        pytest.skip("real SPY cache required")
    config = CodeConfig(universe=["SPY"], timeframe="1d")
    datasets, _ = load_code_data(prices, config)
    rows = [r for r in datasets["SPY"] if "2023-06-30" <= r["session"] <= "2023-07-05"]
    source = algorithm(
        "if e['session']=='2023-07-03' and e['next_sessions'] != "
        "['2023-07-05','2023-07-06']: raise ValueError('calendar mismatch')\nreturn []"
    )
    result = simulate_code(source, config, {"SPY": rows})
    assert len(result["decisions"]) == len(rows) == 3


@MAC
def test_shared_cash_total_cap_on_real_basket():
    directory = ROOT / "data/basket-verification"
    if not directory.exists():
        pytest.skip("real basket cache required")
    config = CodeConfig(universe=["AAPL", "MSFT"], timeframe="1d", max_position_fraction=1)
    data, _ = load_code_data(directory, config)
    config = config.model_copy(update={"max_total_fraction": data["AAPL"][1]["open"] * 1.1 / config.capital})
    source = algorithm(
        "if e['sequence'] != 0: return []\nreturn ["
        "dict(id='a',symbol='AAPL',side='buy',quantity=1),"
        "dict(id='m',symbol='MSFT',side='buy',quantity=1)]"
    )
    result = simulate_code(source, config, {s: rows[:3] for s, rows in data.items()})
    assert result["orders"][0]["status"] == "filled"
    assert result["orders"][1]["reason"] == "total_cap"
    assert result["metrics"]["open_positions"] == {"AAPL": 1, "MSFT": 0}


@MAC
def test_link_style_code_mode_routes_through_codex_without_model_calls(config, tmp_path, monkeypatch, capsys):
    """Exercise the shared import/link/discovery code branch using a frozen real Codex artifact."""
    import sys

    from reddit_strategy_lab.cli import main
    from reddit_strategy_lab.code_generation import CodeGenerator

    artifact = ROOT / "data/generated-code/ni1zuj-8d1aa31c3ada4c14bd3cae8b3af7327a"
    prices = ROOT / "data/market/SPY-2020-2024.csv"
    post = ROOT / "data/posts/ni1zuj.json"
    conf = ROOT / "data/code-hypothesis.json"
    if not all(p.exists() for p in (artifact, prices, post, conf)):
        pytest.skip("retained real Codex artifact/source/prices required")

    def frozen_generation(self, source, code_config, hypotheses=False):
        assert hypotheses
        assert source.id == "ni1zuj"
        return artifact

    monkeypatch.setattr(CodeGenerator, "generate", frozen_generation)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "rsl",
            "import",
            str(post),
            "--code-config",
            str(conf),
            "--hypotheses",
            "--prices",
            str(prices),
            "--out",
            str(tmp_path),
        ],
    )
    main()
    output = json.loads(capsys.readouterr().out)
    assert output["completed"] == 1
    assert output["results"][0]["metrics"]["fills"] == 436
