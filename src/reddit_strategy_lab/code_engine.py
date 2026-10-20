"""Host-owned cash-equity accounting for isolated custom algorithms.

Only real, validated, aligned completed bars enter the worker. Commands at close
are eligible at the following observed open; no intrabar execution is inferred.
"""

import ast
import hashlib
import json
import math
import time
from decimal import Decimal
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from .code_runner import CodeRunner
from .data import load_data
from .schema import Strict, digest


class CodeConfig(Strict):
    version: Literal[1] = 1
    universe: list[str] = Field(min_length=1, max_length=20)
    timeframe: Literal["1min", "5min", "15min", "30min", "1h", "1d"]
    capital: float = Field(default=10000, gt=0, le=1e12, allow_inf_nan=False)
    max_position_fraction: float = Field(default=0.5, gt=0, le=1, allow_inf_nan=False)
    max_total_fraction: float = Field(default=1, gt=0, le=1, allow_inf_nan=False)
    fee_bps: float = Field(default=2, ge=0, le=100, allow_inf_nan=False)
    slippage_bps: float = Field(default=3, ge=0, le=500, allow_inf_nan=False)
    warmup_bars: int = Field(default=0, ge=0, le=10000, strict=True)
    parameters: dict = Field(default_factory=dict)
    execution: Literal["cash_equity_next_open"] = "cash_equity_next_open"
    execution_shift: Literal["none", "close_to_next_open"] = "none"
    formulation: Literal["custom_research", "source_interpretation", "llm_hypothesis"] = "custom_research"
    assumptions: list[str] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def valid(self):
        import re

        if len(set(self.universe)) != len(self.universe) or any(
            not re.fullmatch(r"[A-Z][A-Z0-9.-]{0,9}", s) for s in self.universe
        ):
            raise ValueError("invalid or repeated universe")
        if len(json.dumps(self.parameters, allow_nan=False)) > 16000:
            raise ValueError("parameter size limit exceeded")
        return self


class MarketCommand(Strict):
    id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,64}$")
    symbol: str
    side: Literal["buy", "sell"]
    quantity: int = Field(gt=0, le=1000000000, strict=True)
    type: Literal["market"] = "market"
    valid_for: Literal["next_bar", "same_session"] = "next_bar"


def validate_source(source):
    if len(source.encode()) > 100000:
        raise ValueError("source exceeds 100000 bytes")
    tree = ast.parse(source)
    if not any(isinstance(node, ast.ClassDef) and node.name == "Strategy" for node in tree.body):
        raise ValueError("source must define Strategy(parameters) and on_event(event, portfolio)")
    # Parsing is a syntax check, never a sandbox or semantic approval.


def load_code_data(path, config):
    from types import SimpleNamespace

    path = Path(path)
    files = sorted(path.glob("*.csv")) if path.is_dir() else [path]
    datasets, metadata = {}, {}
    for file in files:
        meta = json.loads(file.with_suffix(".meta.json").read_text())
        symbol = meta["symbol"]
        if symbol not in config.universe:
            continue
        if symbol in datasets:
            raise ValueError("multiple data files for one configured symbol")
        rows, meta = load_data(file, SimpleNamespace(symbol=symbol, timeframe=config.timeframe))
        datasets[symbol], metadata[symbol] = rows, meta
    if set(datasets) != set(config.universe):
        raise ValueError("missing exact-universe real data; no symbol substitution")
    reference = [(r["start"], r["end"]) for r in datasets[config.universe[0]]]
    if any([(r["start"], r["end"]) for r in rows] != reference for rows in datasets.values()):
        raise ValueError("unaligned basket observations; no gap filling or intersection")
    if config.warmup_bars >= len(reference) - 1:
        raise ValueError("insufficient history after warmup")
    return datasets, metadata


def simulate_code(source, config, datasets, runner_factory=CodeRunner):
    """Internal API: datasets must already have passed load_code_data."""
    import exchange_calendars as xcals
    import pandas as pd

    validate_source(source)
    symbols = config.universe
    count = len(datasets[symbols[0]])
    calendar = xcals.get_calendar("XNYS")
    next_sessions = {}
    for row in datasets[symbols[0]]:
        session = row["session"]
        if session not in next_sessions:
            first = calendar.next_session(pd.Timestamp(session))
            second = calendar.next_session(first)
            next_sessions[session] = [first.date().isoformat(), second.date().isoformat()]

    def D(value):
        return Decimal(str(value))

    cash = D(config.capital)
    holdings = dict.fromkeys(symbols, 0)
    fee, slip = D(config.fee_bps) / 10000, D(config.slippage_bps) / 10000
    pending, seen, ledger, decisions, curve = [], set(), [], [], []
    peak = cash
    started = time.monotonic()
    with runner_factory(source, config.parameters) as runner:
        for i in range(count):
            if time.monotonic() - started > 300:
                raise ValueError("whole-run deadline exceeded")
            current = {s: datasets[s][i] for s in symbols}
            reference = current[symbols[0]]
            opens = {s: D(current[s]["open"]) for s in symbols}
            notifications = []
            # Preserve submission order. Every risk check includes earlier accepted fills.
            for command, signal_time, signal_session in pending:
                s, qty = command.symbol, command.quantity
                price = opens[s] * (1 + slip if command.side == "buy" else 1 - slip)
                notional = qty * price
                cost = notional * fee
                reason = None
                if command.valid_for == "same_session" and reference["session"] != signal_session:
                    reason = "session_expired"
                elif command.side == "sell" and qty > holdings[s]:
                    reason = "shorting_forbidden"
                elif command.side == "buy":
                    cash_after = cash - notional - cost
                    marked_after = sum(holdings[n] * opens[n] for n in symbols) + qty * opens[s]
                    equity_after = cash_after + marked_after
                    if cash_after < 0:
                        reason = "insufficient_cash"
                    elif (holdings[s] + qty) * opens[s] > equity_after * D(config.max_position_fraction):
                        reason = "position_cap"
                    elif marked_after > equity_after * D(config.max_total_fraction):
                        reason = "total_cap"
                item = dict(
                    **command.model_dump(),
                    signal_time=signal_time,
                    time=reference["start"].isoformat(),
                    status="rejected" if reason else "filled",
                )
                if reason:
                    item["reason"] = reason
                else:
                    if command.side == "buy":
                        cash -= notional + cost
                        holdings[s] += qty
                    else:
                        cash += notional - cost
                        holdings[s] -= qty
                    item.update(price=float(price), fee=float(cost), cash=float(cash))
                ledger.append(item)
                notifications.append(item)
            pending = []
            if cash < 0 or any(q < 0 for q in holdings.values()):
                raise AssertionError("host cash/position invariant violated")
            equity = cash + sum(holdings[s] * D(current[s]["close"]) for s in symbols)
            peak = max(peak, equity)
            portfolio = dict(cash=float(cash), equity=float(equity), positions=dict(holdings))
            curve.append(
                dict(time=reference["end"].isoformat(), **portfolio, drawdown=float(equity / peak - 1))
            )
            event = dict(
                kind="bar_close",
                sequence=i,
                time=reference["end"].isoformat(),
                session=reference["session"],
                next_sessions=next_sessions[reference["session"]],
                warmup=i < config.warmup_bars,
                bars={
                    s: {k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in current[s].items()}
                    for s in symbols
                },
                order_events=notifications,
            )
            raw = runner.step(event, portfolio)
            if not isinstance(raw, list) or len(raw) > 50:
                raise ValueError("strategy must return at most 50 market commands")
            commands = [MarketCommand.model_validate(c) for c in raw]
            if event["warmup"] and commands:
                raise ValueError("orders during warmup are forbidden")
            for command in commands:
                if command.id in seen or command.symbol not in symbols:
                    raise ValueError("duplicate command ID or unconfigured symbol")
                if len(seen) >= 100000:
                    raise ValueError("whole-run order budget exceeded")
                seen.add(command.id)
                pending.append((command, event["time"], event["session"]))
            decisions.append(
                dict(
                    sequence=i,
                    input_hash=digest(dict(event=event, portfolio=portfolio)),
                    commands=[c.model_dump() for c in commands],
                )
            )
    # Terminal requests cannot fill without another real open. Never force liquidation.
    for command, signal_time, _ in pending:
        ledger.append(
            dict(**command.model_dump(), signal_time=signal_time, status="expired", reason="end_of_data")
        )
    metrics = dict(
        initial_capital=config.capital,
        final_equity=float(equity),
        total_return=float(equity / D(config.capital) - 1),
        max_drawdown=min(point["drawdown"] for point in curve),
        fills=sum(item["status"] == "filled" for item in ledger),
        rejected_orders=sum(item["status"] == "rejected" for item in ledger),
        expired_orders=sum(item["status"] == "expired" for item in ledger),
        open_positions=holdings,
    )
    if not all(math.isfinite(v) for v in metrics.values() if isinstance(v, float)):
        raise ValueError("nonfinite host accounting")
    return dict(metrics=metrics, orders=ledger, curve=curve, decisions=decisions)


def code_hash(source):
    return hashlib.sha256(source.encode()).hexdigest()
