import csv
import json
import math
from datetime import datetime, timedelta
from pathlib import Path

import exchange_calendars as xcals
import pandas as pd

from .schema import digest

INTERVALS = {"1min": 1, "5min": 5, "15min": 15, "30min": 30, "1h": 60, "1d": 1440}


def load_data(path, spec):
    path = Path(path)
    meta = json.loads(path.with_suffix(".meta.json").read_text())
    required = {
        "symbol",
        "timeframe",
        "provider",
        "downloaded_at",
        "adjustment",
        "dividends",
        "survivorship",
        "synthetic",
        "sha256",
    }
    if not required <= meta.keys():
        raise ValueError("incomplete data sidecar metadata")
    import hashlib

    if hashlib.sha256(path.read_bytes()).hexdigest() != meta["sha256"]:
        raise ValueError("data hash mismatch")
    if meta["symbol"] != spec.symbol or meta["timeframe"] != spec.timeframe:
        raise ValueError("requested symbol/timeframe do not match data")
    if meta["adjustment"] not in ("split_adjusted_ohlc",):
        raise ValueError("need consistently split-adjusted OHLC; no mixed adjustment")
    if meta["synthetic"] is not False:
        raise ValueError("synthetic market data is forbidden")
    downloaded = datetime.fromisoformat(meta["downloaded_at"].replace("Z", "+00:00"))
    if downloaded.tzinfo is None:
        raise ValueError("download timestamp needs timezone")
    if any(
        not isinstance(meta[k], str) or not meta[k].strip() for k in ("provider", "dividends", "survivorship")
    ):
        raise ValueError("missing provider/action/universe disclosures")
    calendar = xcals.get_calendar("XNYS")
    rows = []
    with path.open() as f:
        for raw in csv.DictReader(f):
            start = datetime.fromisoformat(raw["start"].replace("Z", "+00:00"))
            end = datetime.fromisoformat(raw["end"].replace("Z", "+00:00"))
            if start.tzinfo is None or end.tzinfo is None or end <= start:
                raise ValueError("invalid or naive bar times")
            day = start.astimezone(__import__("zoneinfo").ZoneInfo("America/New_York")).date()
            session = pd.Timestamp(day)
            if not calendar.is_session(session):
                raise ValueError("bar outside XNYS session")
            opening = calendar.session_open(session).to_pydatetime()
            closing = calendar.session_close(session).to_pydatetime()
            if start < opening or end > closing:
                raise ValueError("extended hours unsupported")
            if spec.timeframe == "1d":
                if start != opening or end != closing:
                    raise ValueError("daily bars must cover entire session")
            elif end - start != timedelta(minutes=INTERVALS[spec.timeframe]):
                raise ValueError("bar duration mismatch")
            vals = {k: float(raw[k]) for k in ("open", "high", "low", "close", "volume")}
            if (
                not all(math.isfinite(v) for v in vals.values())
                or min(vals[k] for k in ("open", "high", "low", "close")) <= 0
                or vals["volume"] < 0
                or vals["volume"] > 1e15
                or max(vals[k] for k in ("open", "high", "low", "close")) > 1e9
            ):
                raise ValueError("invalid market values")
            if (
                vals["low"] > min(vals["open"], vals["close"])
                or vals["high"] < max(vals["open"], vals["close"])
                or vals["low"] > vals["high"]
            ):
                raise ValueError("inconsistent OHLC")
            row = dict(
                vals,
                start=start,
                end=end,
                session=str(day),
                minutes_to_close=(closing - end).total_seconds() / 60,
            )
            if rows:
                prev = rows[-1]
                if start <= prev["start"] or start < prev["end"]:
                    raise ValueError("duplicate, unsorted or overlapping bars")
                if prev["session"] == row["session"]:
                    if start != prev["end"]:
                        raise ValueError("missing intraday bar")
                else:
                    prev_session = pd.Timestamp(prev["session"])
                    if (
                        calendar.next_session(prev_session) != session
                        or start != opening
                        or prev["minutes_to_close"] != 0
                    ):
                        raise ValueError("missing session or boundary bars")
            rows.append(row)
    if len(rows) < 2 or len(rows) > 100000:
        raise ValueError("require 2..100000 bars")
    first_session = pd.Timestamp(rows[0]["session"])
    if (
        rows[0]["start"] != calendar.session_open(first_session).to_pydatetime()
        or rows[-1]["minutes_to_close"] != 0
    ):
        raise ValueError("partial sessions unsupported")
    meta["metadata_hash"] = digest(meta)
    return rows, meta
