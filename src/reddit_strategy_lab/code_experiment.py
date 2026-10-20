"""Frozen custom-code runs and causal prefix checks, with failures retained."""

import hashlib
import html
import json
import os
from pathlib import Path
from uuid import uuid4

from .code_engine import CodeConfig, code_hash, load_code_data, simulate_code, validate_source
from .code_runner import verify_sandbox
from .collection import now
from .schema import digest


def implementation_hashes():
    return {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(Path(__file__).parent.glob("*.py"))
    }


LOADED_IMPLEMENTATION = implementation_hashes()


def save_json(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def register(root, record):
    line = (json.dumps(record, allow_nan=False) + "\n").encode()
    fd = os.open(root / "trials.jsonl", os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o600)
    try:
        if os.write(fd, line) != len(line):
            raise OSError("incomplete trial registry write")
        os.fsync(fd)
    finally:
        os.close(fd)


def run_code_file(source_path, config_path, prices, out):
    if implementation_hashes() != LOADED_IMPLEMENTATION:
        raise ValueError("implementation changed during this process; restart before freezing a run")
    source = Path(source_path).read_text()
    validate_source(source)
    config = CodeConfig.model_validate_json(Path(config_path).read_text())
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    run_id = uuid4().hex
    folder = out / run_id
    folder.mkdir()
    (folder / "strategy.py").write_text(source)
    save_json(folder / "config.json", config.model_dump())
    identity = dict(run_id=run_id, code_hash=code_hash(source), config_hash=digest(config.model_dump()))
    register(out, dict(**identity, time=now(), status="started"))
    try:
        datasets, metadata = load_code_data(prices, config)
        boundary = verify_sandbox()
        import platform
        import sys

        engine_hashes = LOADED_IMPLEMENTATION
        manifest = dict(
            **identity,
            frozen_at=now(),
            config=config.model_dump(),
            data=metadata,
            engine_hashes=engine_hashes,
            runtime=dict(python=sys.version, platform=platform.platform()),
            isolation=boundary,
            evaluation="retrospective research; no sealed holdout claimed",
            protocol="completed-aligned-bars-v1",
            execution="next-observed-open-market-v1",
            limitations=[
                "cash long-only equities; fixed universe; no stops/shorts/FX",
                "whole-order fills assume liquidity; no volume/queue/market-impact reconstruction",
                "split-adjusted price returns; dividends excluded",
                "caps apply at buys; subsequent market drift may exceed them",
                "prefix agreement is a regression check, not proof against all leakage/overfitting",
            ],
        )
        provenance = Path(str(source_path) + ".metadata.json")
        if provenance.exists():
            generated = json.loads(provenance.read_text())
            if (
                generated.get("code_hash") != identity["code_hash"]
                or generated.get("config_hash") != identity["config_hash"]
            ):
                raise ValueError(
                    "generated code/config differs from its provenance; create a new reviewed artifact"
                )
            manifest["generation"] = generated
        save_json(folder / "manifest.json", manifest)
        for name in ("strategy.py", "config.json", "manifest.json"):
            (folder / name).chmod(0o444)
        result = simulate_code(source, config, datasets)
        count = len(result["decisions"])
        cutoff = max(1, count // 2)
        prefix = simulate_code(source, config, {s: rows[:cutoff] for s, rows in datasets.items()})
        if prefix["decisions"] != result["decisions"][:cutoff]:
            raise ValueError("causal prefix replay disagrees; performance withheld")
        result["audit"] = dict(prefix_events=cutoff, prefix_match=True, future_observations_delivered=False)
        save_json(folder / "result.json", result)
        metrics = result["metrics"]
        report = f"""<!doctype html><html lang="en"><meta charset="utf-8"><title>Custom strategy run</title>
<style>body{{font:17px system-ui;max-width:900px;margin:45px auto;padding:20px;line-height:1.6}}
pre{{white-space:pre-wrap;background:#f4f5f7;padding:20px}}a{{color:#245bc1}}</style>
<h1>Custom strategy research</h1><p>Isolated Python decisions; host-owned execution and accounting.</p>
<p>Retrospective simulation. No profitability, fidelity, or overfitting guarantee.</p>
<h2>Host-calculated results</h2><pre>{html.escape(json.dumps(metrics, indent=2))}</pre>
<h2>Verification</h2><p>Fresh-worker prefix replay matched the first {cutoff} events.
File contents, writes, network and process-fork probes were denied. No credentials inherited.</p>
<h2>Execution limits</h2><ul>{"".join("<li>" + html.escape(x) + "</li>" for x in manifest["limitations"])}</ul>
<p>macOS memory monitoring is best effort; this is a local research backend, not a hardened multi-tenant service.</p>
<h2>Declared assumptions</h2><pre>{html.escape(json.dumps(config.assumptions, indent=2))}</pre>
<p><a href="manifest.json">Frozen manifest</a> · <a href="result.json">Orders, decisions and equity</a> ·
<a href="strategy.py">Exact strategy source</a> · <a href="config.json">Configuration</a></p></html>"""
        (folder / "report.html").write_text(report)
        save_json(
            folder / "artifacts.json",
            {
                p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted(folder.iterdir())
                if p.is_file()
            },
        )
        register(out, dict(**identity, time=now(), status="completed", manifest_hash=digest(manifest)))
        return folder, metrics
    except BaseException as exc:
        # Error values and generated code may contain arbitrary text; retain only type.
        save_json(folder / "failure.json", dict(error_type=type(exc).__name__, performance_withheld=True))
        register(out, dict(**identity, time=now(), status="failed", error_type=type(exc).__name__))
        raise
