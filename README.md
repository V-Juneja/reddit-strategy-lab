# Reddit Strategy Lab

Turn real Reddit strategy posts into reviewed custom Python algorithms, host-regulated historical simulations and static research reports. The installed, signed-in Codex CLI reads the source and writes each strategy; the host alone supplies real market observations, validates commands, applies fills/costs and reports results.

`real post → Codex source contract → custom strategy code → sandboxed host execution → report`

The project contains two reviewed [2020–2024 real-SPY case studies](docs/case-studies.md). Their results are retrospective, use stated assumptions and are not evidence of a future edge. Open the [visual report](examples/reports/2020-2024/index.html) and its [frozen window record](configs/research-window-2020-2024.json).

![Retrospective equity from the two-down-close case](examples/reports/post-1x8o01e/equity.png)

## Setup

```sh
python3 -m pip install --user uv
python3 -m uv sync --locked
python3 -m uv run rsl check-access
python3 -m uv run rsl check-code-sandbox
```

Codex uses the existing local ChatGPT/Codex sign-in. No model API key is read by this repository. Reddit link and discovery commands require approved OAuth access; copy `.env.example` to `.env` and supply only the approved Reddit values.

## Autonomous discovery

Discovery is bounded and auditable. It rotates through new/top/hot listings and diversified rule searches, records every collected post and exclusion, and only backtests a source when its explicit instrument universe and timeframe match a fixed configuration with real corresponding data. It never substitutes SPY for an unsupported or missing source instrument.

```sh
# Check that Codex and approved Reddit access are both ready.
python3 -m uv run rsl check-access

# Collect a real candidate batch first. This makes no model calls and no backtests.
python3 -m uv run rsl discover --subreddit algotrading,stocks --limit 20 \
  --feeds new,top,hot --max-reddit-requests 12 --collect-only

# Translate and test eligible candidates with a fixed universe configuration.
python3 -m uv run rsl discover --subreddit algotrading --limit 10 \
  --code-config configs/code-post-1x8o01e.json \
  --prices data/market/SPY-2020-01-01-2025-01-01.csv --hypotheses
```

`--collect-only` saves a versioned local candidate batch. The full command then asks Codex to extract a source contract, generates and independently reviews strategy code before the host gets prices, and reports each candidate as completed or excluded. Exclusions are expected when a post needs unsupported mechanisms, unspecified critical details, or data outside the fixed configuration.

## Supply a link or local source

```sh
python3 -m uv run rsl link 'https://www.reddit.com/r/algotrading/comments/POST_ID/' \
  --code-config configs/code-post-1x8o01e.json \
  --prices data/market/SPY-2020-01-01-2025-01-01.csv --hypotheses

python3 -m uv run rsl extract data/posts.json \
  --code-config configs/code-post-1x8o01e.json --hypotheses
```

Faithful mode abstains when a post omits critical facts. `--hypotheses` permits only the explicit assumptions recorded in the fixed configuration; the model never receives price outcomes or backtest feedback before code is frozen.

## Real prices and verification

```sh
python3 -m uv run rsl fetch-prices --start 2020-01-01 --end 2025-01-01
python3 -m uv run pytest -q
python3 -m uv run ruff check .
python3 -m uv run ruff format --check .
python3 -m uv run python scripts/check_public_safety.py
```

The downloader accepts explicit US stock/ETF symbols and real daily Yahoo observations. No synthetic observations, interpolation or symbol proxies are used. Custom strategy code runs in the macOS sandbox, sees only completed bars and a bounded portfolio snapshot, and returns typed order commands. The host owns next-open fills, cash, whole shares, fees, slippage and exposure caps.

## Repository browser

```sh
python3 scripts/serve_tracked_repo.py
```

Open `http://127.0.0.1:8772/` to click through tracked files without exposing ignored market data, source imports, credentials or run caches.

Read the [custom-code design](docs/custom-code.md), [architecture](docs/custom-strategy-architecture.md), [methodology](docs/methodology.md), and [publishing checklist](docs/publishing-checklist.md).
