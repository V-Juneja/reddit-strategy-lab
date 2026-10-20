"""Small real-data adapter. SPY only; other instruments require validated local exports."""

import csv
import hashlib
import json
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, build_opener

import exchange_calendars as xcals
import pandas as pd

from .collection import NoRedirect, now


def fetch_spy(start, end, output, symbol="SPY"):
    import re

    if not re.fullmatch(r"[A-Z][A-Z0-9.-]{0,9}", symbol):
        raise ValueError("invalid market symbol")
    first, last = date.fromisoformat(start), date.fromisoformat(end)
    if first >= last or (last - first).days > 3653:
        raise ValueError("request an increasing period of at most 10 years")
    root = Path(output)
    root.mkdir(parents=True, exist_ok=True)
    target = root / f"{symbol}-{start}-{end}.csv"
    if target.exists():
        # Never silently overwrite research data. load_data verifies the hash during runs.
        if not target.with_suffix(".meta.json").exists():
            raise ValueError("cached price metadata is missing")
        return target
    params = dict(
        period1=int(datetime.combine(first, datetime.min.time(), timezone.utc).timestamp()),
        period2=int(datetime.combine(last, datetime.min.time(), timezone.utc).timestamp()),
        interval="1d",
        events="div,splits",
    )
    req = Request(
        "https://query1.finance.yahoo.com/v8/finance/chart/" + symbol + "?" + urlencode(params),
        headers={"User-Agent": "reddit-strategy-lab/0.1 personal-research"},
    )
    with build_opener(NoRedirect).open(req, timeout=30) as response:
        raw = response.read(5_000_001)
    if len(raw) > 5_000_000:
        raise ValueError("market response exceeds budget")
    result = json.loads(raw)["chart"]["result"][0]
    if result["meta"]["symbol"] != symbol or result.get("events", {}).get("splits"):
        raise ValueError("symbol mismatch or split event requires separately verified export")
    quotes = result["indicators"]["quote"][0]
    cal = xcals.get_calendar("XNYS")
    rows = []
    for i, timestamp in enumerate(result["timestamp"]):
        day = pd.Timestamp(datetime.fromtimestamp(timestamp, timezone.utc).date())
        if not first <= day.date() < last:
            raise ValueError("provider returned out-of-range observation")
        values = {k: quotes[k][i] for k in ("open", "high", "low", "close", "volume")}
        if any(v is None for v in values.values()):
            raise ValueError("missing observed market data; interpolation forbidden")
        rows.append(
            dict(start=cal.session_open(day).isoformat(), end=cal.session_close(day).isoformat(), **values)
        )
    if not rows:
        raise ValueError("no actual market observations")
    with target.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    raw_path = target.with_suffix(".provider.json")
    raw_path.write_bytes(raw)
    meta = dict(
        symbol=symbol,
        timeframe="1d",
        provider="Yahoo Finance chart endpoint; personal research; availability and licensing subject to provider terms",
        downloaded_at=now(),
        adjustment="split_adjusted_ohlc",
        dividends="excluded; use Yahoo quote OHLC, never mix with dividend-adjusted Adj Close",
        survivorship="explicit current security; no delisted-stock or historical universe reconstruction",
        synthetic=False,
        sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
        raw_sha256=hashlib.sha256(raw).hexdigest(),
        split_events_in_period=0,
    )
    target.with_suffix(".meta.json").write_text(json.dumps(meta, indent=2))
    return target
