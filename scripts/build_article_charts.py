"""Build clean Matplotlib charts for the first newsletter case study."""

from __future__ import annotations

import csv
import json
import math
from datetime import datetime
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
PRICE_FILE = ROOT / "data/market/SPY-2020-01-01-2025-01-01.csv"
RUN_FILE = ROOT / "runs/custom-code/3b71251d0a3e4512b2fcfcca06a9ac76/result.json"
OUT = ROOT / "examples/reports/post-1x8o01e"
INITIAL_CASH = 10_000.0
FEE_BPS = 2.0
SLIPPAGE_BPS = 3.0


def main() -> None:
    prices = list(csv.DictReader(PRICE_FILE.open()))
    result = json.loads(RUN_FILE.read_text())
    dates = [datetime.fromisoformat(row["end"]) for row in prices]
    strategy = np.array([float(point["equity"]) for point in result["curve"]])
    if len(prices) != len(strategy):
        raise ValueError("Price rows and strategy curve have different lengths")

    # Match the project's stated single-entry SPY buy-and-hold baseline:
    # first eligible next-open fill, whole shares, then mark at each close.
    first = next(i for i, row in enumerate(prices) if row["start"].startswith("2020-01-07"))
    fill = float(prices[first]["open"]) * (1 + SLIPPAGE_BPS / 10_000)
    shares = math.floor(INITIAL_CASH / (fill * (1 + FEE_BPS / 10_000)))
    cash = INITIAL_CASH - shares * fill * (1 + FEE_BPS / 10_000)
    benchmark = np.array(
        [INITIAL_CASH if i < first else cash + shares * float(row["close"]) for i, row in enumerate(prices)]
    )

    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 10,
            "axes.titlesize": 13,
            "axes.titleweight": "regular",
            "axes.labelsize": 10,
            "legend.frameon": False,
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "savefig.facecolor": "white",
        }
    )

    navy = "#315f89"
    orange = "#d47a36"
    gray = "#777777"
    grid = "#dedede"

    def clean_axes(ax: plt.Axes) -> None:
        ax.grid(axis="y", color=grid, linewidth=0.7)
        ax.set_axisbelow(True)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_color("#aaaaaa")
        ax.spines["bottom"].set_color("#aaaaaa")
        ax.xaxis.set_major_locator(mdates.YearLocator())
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))

    OUT.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(10.5, 5.2))
    ax.plot(dates, benchmark, color=navy, linewidth=1.9, label="SPY buy-and-hold")
    ax.plot(dates, strategy, color=orange, linewidth=1.9, label="Reddit-sourced rule")
    ax.axhline(INITIAL_CASH, color=gray, linestyle="--", linewidth=1.0, label="Starting balance")
    fig.text(0.105, 0.965, "SPY: Reddit-sourced rule vs. buy-and-hold", ha="left", va="top", fontsize=14)
    fig.text(
        0.105,
        0.92,
        "Daily prices · 2020–2024 · $10,000 start · dividends excluded",
        ha="left",
        va="top",
        fontsize=9,
        color="#555555",
    )
    ax.set_ylabel("Account value ($)")
    ax.set_xlabel("Year")
    ax.yaxis.set_major_formatter(mticker.StrMethodFormatter("${x:,.0f}"))
    ax.legend(loc="upper left", ncol=3)
    clean_axes(ax)
    fig.subplots_adjust(left=0.105, right=0.98, bottom=0.13, top=0.86)
    fig.savefig(OUT / "article-equity-vs-spy.png", dpi=180, bbox_inches="tight")
    plt.close(fig)

    strat_dd = (strategy / np.maximum.accumulate(strategy) - 1) * 100
    bench_dd = (benchmark / np.maximum.accumulate(benchmark) - 1) * 100
    fig, ax = plt.subplots(figsize=(10.5, 3.7))
    ax.fill_between(dates, strat_dd, 0, color=orange, alpha=0.15)
    ax.plot(dates, strat_dd, color=orange, linewidth=1.5, label="Reddit-sourced rule")
    ax.plot(dates, bench_dd, color=navy, linewidth=1.5, label="SPY buy-and-hold")
    ax.set_title("Drawdown over the same test window", loc="left", pad=12)
    ax.set_ylabel("From prior peak (%)")
    ax.set_xlabel("Year")
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(xmax=100))
    ax.legend(loc="lower left", ncol=2)
    clean_axes(ax)
    ax.set_ylim(min(float(strat_dd.min()), float(bench_dd.min())) - 3, 1)
    fig.tight_layout()
    fig.savefig(OUT / "article-drawdown-vs-spy.png", dpi=180, bbox_inches="tight")
    plt.close(fig)

    print(f"strategy end: ${strategy[-1]:,.2f} ({(strategy[-1] / INITIAL_CASH - 1):.2%})")
    print(f"buy-and-hold end: ${benchmark[-1]:,.2f} ({(benchmark[-1] / INITIAL_CASH - 1):.2%})")
    print(f"strategy max drawdown: {strat_dd.min():.2f}%")
    print(f"buy-and-hold max drawdown: {bench_dd.min():.2f}%")
    print(f"saved charts to {OUT}")


if __name__ == "__main__":
    main()
