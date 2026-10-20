"""Publish a small, reviewed static case from a completed local custom-code run.

The raw Reddit text, model transcripts, market bars and order-level records stay local.
Review the output before committing it; this script does not certify source fidelity.
"""

import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.dates import AutoDateLocator, ConciseDateFormatter


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path, help="completed local runs/custom-code/<id> directory")
    parser.add_argument("out", type=Path, help="public examples/reports/<post-id> directory")
    parser.add_argument("--title", required=True)
    args = parser.parse_args()

    run = args.run
    result = json.loads((run / "result.json").read_text())
    manifest = json.loads((run / "manifest.json").read_text())
    generated = manifest.get("generation")
    if not generated or generated["review"].get("passes") is not True:
        raise ValueError("case requires a source-linked, model-reviewed generated run")
    if result.get("audit", {}).get("prefix_match") is not True:
        raise ValueError("case requires a successful fresh-worker prefix check")
    curve = result["curve"]
    if not curve:
        raise ValueError("completed case has no equity observations")
    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    xs = [datetime.fromisoformat(point["time"]) for point in curve]
    for stem, field, ylabel, multiplier in (
        ("equity", "equity", "Equity (USD)", 1),
        ("drawdown", "drawdown", "Drawdown (%)", 100),
    ):
        fig, ax = plt.subplots(figsize=(9, 3.6), layout="constrained")
        ax.plot(xs, [point[field] * multiplier for point in curve], color="#176b8a", lw=1.5)
        ax.set(title=f"{args.title} · retrospective simulation", xlabel="Bar end", ylabel=ylabel)
        ax.xaxis.set_major_locator(AutoDateLocator())
        ax.xaxis.set_major_formatter(ConciseDateFormatter(ax.xaxis.get_major_locator()))
        ax.grid(alpha=0.25)
        fig.savefig(out / f"{stem}.png", dpi=150)
        plt.close(fig)

    shutil.copyfile(run / "strategy.py", out / "strategy.py")
    shutil.copyfile(run / "config.json", out / "config.json")
    metrics = result["metrics"]
    meta = next(iter(manifest["data"].values()))
    assumptions = "\n".join(f"- {line}" for line in manifest["config"]["assumptions"])
    limitations = "\n".join(f"- {line}" for line in manifest["limitations"])
    final_positions = ", ".join(f"{s}: {q}" for s, q in metrics["open_positions"].items())
    report = f"""# {args.title}

Source: [original Reddit post]({generated["source_url"]}). This is a **source-inspired interpretation** with disclosed assumptions; it is not the author's original trade record or a claim of a tradable edge.

Codex model: `{generated["generation"]["model"]}`. Independent model review: passed. Host's fresh-worker causal prefix replay: passed. [Human trade-level checks](../../../docs/case-studies.md) compared every recorded order with the real price bars. The model received source text and interface rules, but no market prices or performance feedback before code was frozen.

| Measure | Result |
| --- | ---: |
| Real price observations | {len(curve):,} |
| Sample | {xs[0].date()} to {xs[-1].date()} |
| Initial capital | ${metrics["initial_capital"]:,.2f} |
| Final marked equity | ${metrics["final_equity"]:,.2f} |
| Total price return after configured costs | {metrics["total_return"]:.2%} |
| Maximum bar-close drawdown | {metrics["max_drawdown"]:.2%} |
| Filled orders | {metrics["fills"]} |
| Rejected orders | {metrics["rejected_orders"]} |
| Expired orders | {metrics["expired_orders"]} |
| Final open shares | {final_positions} |

The sample predates this post. It is retrospective and was **not** an untouched holdout. The public charts are static exports; raw provider prices, full source body, model transcripts, and the complete order ledger remain local.

Code SHA256: `{manifest["code_hash"]}`. Real market CSV SHA256: `{meta["sha256"]}`. Price source: {meta["provider"]}. {meta["dividends"]}. Fills use the next observed market open with configured slippage and fees; cash, positions and caps are enforced by the host.

## Declared assumptions

{assumptions}

## Engine limits

{limitations}

[Exact reviewed strategy code](strategy.py) · [Frozen configuration](config.json)

![Retrospective equity curve](equity.png)

![Retrospective drawdown](drawdown.png)
"""
    (out / "report.md").write_text(report)
    print(out / "report.md")


if __name__ == "__main__":
    main()
