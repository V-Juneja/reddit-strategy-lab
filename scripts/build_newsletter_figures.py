"""Build plain Matplotlib figures for the newsletter case studies."""

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
PRICE_PATH = ROOT / "data/market/SPY-2020-01-01-2025-01-01.csv"
TWO_DOWN_PATH = ROOT / "runs/custom-code/3b71251d0a3e4512b2fcfcca06a9ac76/result.json"
TUESDAY_PATH = ROOT / "runs/custom-code/0b059922875a450cbf9ec9f9216f24c3/result.json"
CLOSE_NEAR_LOW_PATH = ROOT / "runs/custom-code/44e6728ccb594014bcede48d09bbaaa7/result.json"
OUT = ROOT / "examples/reports/2020-2024"
TWO_DOWN_OUT = ROOT / "examples/reports/post-1x8o01e"
TUESDAY_OUT = ROOT / "examples/reports/post-1wmxzw7"


def load_curve(path: Path) -> np.ndarray:
    payload = json.loads(path.read_text())
    return np.array([float(item["equity"]) for item in payload["curve"]])


def load_data() -> tuple[list[datetime], list[dict[str, str]], np.ndarray, np.ndarray, np.ndarray]:
    prices = list(csv.DictReader(PRICE_PATH.open()))
    two_down = load_curve(TWO_DOWN_PATH)
    tuesday = load_curve(TUESDAY_PATH)
    if len(prices) != len(two_down) or len(prices) != len(tuesday):
        raise ValueError("Price and strategy curves have different lengths")

    dates = [datetime.fromisoformat(row["end"]) for row in prices]
    first_eligible = next(index for index, row in enumerate(prices) if row["start"].startswith("2020-01-07"))
    open_price = float(prices[first_eligible]["open"])
    buy_price = open_price * (1 + 3 / 10_000)
    shares = math.floor(10_000 / (buy_price * (1 + 2 / 10_000)))
    cash = 10_000 - shares * buy_price * (1 + 2 / 10_000)
    buy_hold = np.array(
        [
            10_000.0 if index < first_eligible else cash + shares * float(row["close"])
            for index, row in enumerate(prices)
        ]
    )
    print(f"SPY buy-and-hold: {shares} shares, ${cash:.2f} residual cash")
    print(f"SPY buy-and-hold final equity: ${buy_hold[-1]:,.2f}")
    return dates, prices, two_down, tuesday, buy_hold


def style(ax: plt.Axes) -> None:
    ax.grid(True, color="#d9d9d9", linewidth=0.7, alpha=0.7)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.set_axisbelow(True)


def money_axis(ax: plt.Axes) -> None:
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda value, _: f"${value:,.0f}"))


def save(fig: plt.Figure, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path, dpi=170, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def drawdown(values: np.ndarray) -> np.ndarray:
    peak = np.maximum.accumulate(values)
    return (values / peak - 1) * 100


def main() -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 10,
            "axes.titlesize": 14,
            "axes.titleweight": "regular",
            "axes.labelsize": 10,
            "legend.frameon": False,
            "figure.facecolor": "white",
            "axes.facecolor": "white",
        }
    )
    dates, prices, two_down, tuesday, buy_hold = load_data()
    OUT.mkdir(parents=True, exist_ok=True)

    # Shared comparison.
    fig, ax = plt.subplots(figsize=(10.5, 5.2))
    ax.plot(dates, buy_hold, linewidth=2, label="SPY buy-and-hold")
    ax.plot(dates, two_down, linewidth=2, label="Two down closes")
    ax.plot(dates, tuesday, linewidth=1.8, label="Turnaround Tuesday")
    ax.axhline(10_000, color="#777777", linestyle="--", linewidth=1, label="Starting balance")
    ax.set_title("Three strategies, same SPY prices and starting balance", loc="left")
    ax.set_ylabel("Account value ($)")
    ax.set_xlabel("Date")
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.yaxis.set_major_formatter(mticker.StrMethodFormatter("${x:,.0f}"))
    ax.legend(loc="upper left", ncol=2)
    style(ax)
    save(fig, OUT / "newsletter-strategy-vs-spy.png")

    # Individual account curves and drawdowns.
    for curve, name, folder in (
        (two_down, "Two down closes", TWO_DOWN_OUT),
        (tuesday, "Turnaround Tuesday", TUESDAY_OUT),
    ):
        fig, ax = plt.subplots(figsize=(10.5, 4.8))
        ax.plot(dates, curve, color="#1f77b4", linewidth=1.8)
        ax.axhline(10_000, color="#777777", linestyle="--", linewidth=1)
        ax.set_title(f"{name}: account value", loc="left")
        ax.set_ylabel("Account value ($)")
        ax.set_xlabel("Date")
        ax.xaxis.set_major_locator(mdates.YearLocator())
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
        ax.yaxis.set_major_formatter(mticker.StrMethodFormatter("${x:,.0f}"))
        style(ax)
        save(fig, folder / "equity.png")

        dd = drawdown(curve)
        fig, ax = plt.subplots(figsize=(10.5, 3.8))
        ax.fill_between(dates, dd, 0, color="#d62728", alpha=0.22)
        ax.plot(dates, dd, color="#d62728", linewidth=1.5)
        ax.set_title(f"{name}: drawdown", loc="left")
        ax.set_ylabel("Drawdown (%)")
        ax.set_xlabel("Date")
        ax.xaxis.set_major_locator(mdates.YearLocator())
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
        ax.yaxis.set_major_formatter(mticker.PercentFormatter(xmax=100))
        ax.set_ylim(min(-20, float(dd.min()) - 2), 1)
        style(ax)
        save(fig, folder / "drawdown.png")

    # Calendar-year returns.
    years = range(2020, 2025)
    year_ends = [max(i for i, date in enumerate(dates) if date.year == year) for year in years]
    series = [("SPY buy-and-hold", buy_hold), ("Two down closes", two_down), ("Turnaround Tuesday", tuesday)]
    yearly: list[list[float]] = []
    for _, values in series:
        previous = 10_000.0
        annual = []
        for end in year_ends:
            current = float(values[end])
            annual.append((current / previous - 1) * 100)
            previous = current
        yearly.append(annual)

    x = np.arange(len(year_ends))
    width = 0.24
    fig, ax = plt.subplots(figsize=(10, 5))
    colors = ["#1f77b4", "#ff7f0e", "#2ca02c"]
    for offset, ((name, _), values, color) in enumerate(zip(series, yearly, colors, strict=True)):
        ax.bar(x + (offset - 1) * width, values, width, label=name, color=color)
    ax.axhline(0, color="#555555", linewidth=0.9)
    ax.set_title("Calendar-year returns", loc="left")
    ax.set_ylabel("Return (%)")
    ax.set_xlabel("Year")
    ax.set_xticks(x, [str(year) for year in years])
    ax.legend(loc="upper left", ncol=3)
    style(ax)
    save(fig, OUT / "newsletter-year-by-year.png")

    # Executable next-open interpretation for the close-near-low signal.
    close_curve = load_curve(CLOSE_NEAR_LOW_PATH)
    if len(close_curve) != len(dates):
        raise ValueError("Close-near-low curve has a different length")
    fig, ax = plt.subplots(figsize=(10.5, 4.8))
    ax.plot(dates, close_curve, color="#d62728", linewidth=1.8, label="Next-open SPY version")
    ax.axhline(10_000, color="#555555", linestyle="--", linewidth=1, label="Starting balance")
    ax.set_title("Close-near-low strategy: next-open interpretation", loc="left")
    ax.set_ylabel("Account value ($)")
    ax.set_xlabel("Date")
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.yaxis.set_major_formatter(mticker.StrMethodFormatter("${x:,.0f}"))
    ax.legend(loc="upper left")
    style(ax)
    save(fig, OUT / "newsletter-close-near-low-interpretation.png")

    # Descriptive event study: yearly hit rates and full-sample baseline.
    years_to_plot = list(range(2020, 2025))
    signal_counts: list[int] = []
    hit_rates: list[float] = []
    all_counts: list[int] = []
    all_positive: list[int] = []
    for year in years_to_plot:
        outcomes: list[bool] = []
        all_outcomes: list[bool] = []
        for index, row in enumerate(prices[:-1]):
            high, low, close = (float(row[key]) for key in ("high", "low", "close"))
            next_close = float(prices[index + 1]["close"])
            if datetime.fromisoformat(row["end"]).year != year or high <= low:
                continue
            up = next_close > close
            all_outcomes.append(up)
            if (close - low) / (high - low) < 0.20:
                outcomes.append(up)
        signal_counts.append(len(outcomes))
        hit_rates.append(sum(outcomes) / len(outcomes) if outcomes else 0.0)
        all_counts.append(len(all_outcomes))
        all_positive.append(sum(all_outcomes))
    baseline = sum(all_positive) / sum(all_counts)

    fig, ax = plt.subplots(figsize=(9.5, 4.8))
    bars = ax.bar(
        years_to_plot, np.array(hit_rates) * 100, color="#1f77b4", width=0.62, label="Close-near-low signals"
    )
    ax.axhline(
        baseline * 100, color="#ff7f0e", linestyle="--", linewidth=1.8, label=f"All SPY days ({baseline:.1%})"
    )
    for bar, n in zip(bars, signal_counts, strict=True):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 1.2,
            f"n={n}",
            ha="center",
            va="bottom",
            fontsize=8,
            color="#444444",
        )
    ax.set_title("Next-day positive closes after a close near the low", loc="left")
    ax.set_ylabel("Share of next closes above signal-day close (%)")
    ax.set_xlabel("Year")
    ax.set_xticks(years_to_plot)
    ax.set_ylim(0, 82)
    ax.legend(loc="upper right")
    style(ax)
    save(fig, OUT / "newsletter-close-near-low-event-study.png")

    for (name, _), values in zip(series, yearly, strict=True):
        print(
            name,
            ", ".join(
                f"{year}: {value:+.2f}%" for year, value in zip(range(2020, 2025), values, strict=True)
            ),
        )


if __name__ == "__main__":
    main()
