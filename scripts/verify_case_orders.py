"""Independently check source-rule timing and host fills against real CSV bars."""

import argparse
import csv
import json
import math
from datetime import date
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case", choices=["two-down", "turnaround-tuesday"])
    parser.add_argument("run", type=Path, help="completed custom-code run directory")
    parser.add_argument("prices", type=Path, help="the exact real SPY CSV used by the run")
    args = parser.parse_args()
    result = json.loads((args.run / "result.json").read_text())
    manifest = json.loads((args.run / "manifest.json").read_text())
    if (
        manifest["data"]["SPY"]["sha256"]
        != __import__("hashlib").sha256(args.prices.read_bytes()).hexdigest()
    ):
        raise ValueError("price CSV differs from frozen run")
    with args.prices.open() as f:
        rows = list(csv.DictReader(f))
    ends = {r["end"]: i for i, r in enumerate(rows)}
    starts = {r["start"]: i for i, r in enumerate(rows)}
    if len(ends) != len(rows) or len(starts) != len(rows):
        raise ValueError("duplicate bar timestamps")
    entry = None
    buys = sells = rejected = 0
    fee = manifest["config"]["fee_bps"] / 10000
    slip = manifest["config"]["slippage_bps"] / 10000
    for order in result["orders"]:
        signal = ends[order["signal_time"]]
        fill_bar = starts[order["time"]]
        assert fill_bar == signal + 1, order
        signal_day = date.fromisoformat(rows[signal]["start"][:10])
        fill_day = date.fromisoformat(rows[fill_bar]["start"][:10])
        if order["side"] == "buy":
            if args.case == "two-down":
                assert signal >= 2
                assert (
                    float(rows[signal]["close"])
                    < float(rows[signal - 1]["close"])
                    < float(rows[signal - 2]["close"])
                ), order
            else:
                assert signal_day.weekday() == 0 and signal >= 1
                friday = date.fromisoformat(rows[signal - 1]["start"][:10])
                assert friday.weekday() == 4 and (signal_day - friday).days == 3, order
                assert float(rows[signal]["close"]) < float(rows[signal - 1]["close"]), order
                assert fill_day.weekday() == 1 and (fill_day - signal_day).days == 1, order
            if order["status"] == "filled":
                assert entry is None, order
                entry = fill_bar
                buys += 1
            else:
                assert order["status"] == "rejected", order
                rejected += 1
        else:
            assert order["side"] == "sell" and order["status"] == "filled" and entry is not None
            if args.case == "two-down":
                assert fill_bar - entry == 5, order
            else:
                assert signal == entry and fill_bar == entry + 1 and fill_day.weekday() == 2, order
            entry = None
            sells += 1
        if order["status"] == "filled":
            direction = 1 if order["side"] == "buy" else -1
            expected_price = float(rows[fill_bar]["open"]) * (1 + direction * slip)
            expected_fee = expected_price * order["quantity"] * fee
            assert math.isclose(order["price"], expected_price, rel_tol=1e-12), order
            assert math.isclose(order["fee"], expected_fee, rel_tol=1e-12), order
    assert buys + sells == result["metrics"]["fills"]
    assert rejected == result["metrics"]["rejected_orders"]
    assert (entry is not None) == (result["metrics"]["open_positions"]["SPY"] > 0)
    print(json.dumps(dict(case=args.case, filled_buys=buys, filled_sells=sells, rejected_buys=rejected)))


if __name__ == "__main__":
    main()
