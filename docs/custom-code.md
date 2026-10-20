# Custom Python strategies

Implemented local research backend: arbitrary Python computations and persistent strategy state, isolated from host data and accounting. The current execution capability is cash, long-only US stocks/ETFs, an explicit basket, regular-session completed bars and whole-share market orders at the next recorded open. Unsupported order fields and mechanics fail; no FX, shorts, intrabar stops, leverage or invented intrabar paths are enabled.

## Run code

```sh
python3 -m uv run rsl check-code-sandbox
python3 -m uv run rsl run-code examples/custom-code/cross_sectional.py \
  --config examples/custom-code/config.json \
  --prices data/basket-verification
```

The example needs real AAPL, MSFT and AMZN daily CSVs with verified sidecars in that directory. It is an engine demonstration, not a Reddit reproduction or evidence of a profitable strategy. It ranks the basket using a custom downside-sensitive momentum calculation and keeps rolling state in ordinary Python. You can write completely different algorithms against the same interface.

```python
class Strategy:
    def __init__(self, parameters):
        self.observations = {}

    def on_event(self, event, portfolio):
        # Compute from already-delivered observations; maintain arbitrary state.
        # Return [] or a list of order requests. The engine owns actual fills.
        return []
```

`event` includes `kind='bar_close'`, `sequence`, completed-bar `time`, `session`, `warmup`, `bars` keyed by symbol, and `order_events` from this bar's open. It also supplies `next_sessions`, the next two scheduled XNYS session dates known from the exchange calendar; this lets weekday strategies skip holiday weeks without seeing future prices. Each bar contains OHLCV, start/end timestamps, session and minutes_to_close. `portfolio` supplies cash, marked equity and actual integer positions. No future rows, file paths, final run date, total row count, credentials or host objects enter the worker.

A command is `{id, symbol, side, quantity, type: 'market', valid_for: 'next_bar'}`. IDs must be globally unique, 1–64 alphanumeric/underscore/hyphen characters. Quantities are positive integers. `valid_for='same_session'` prevents a pre-close entry from spilling into the next session. At most 50 commands per callback and 100,000 per run. Orders during warmup, extra fields, unconfigured symbols and duplicate IDs stop the run. Full-size orders that violate cash/position/total caps or try to sell unowned shares are rejected with an order event. They are not silently resized. Order sequence is preserved; submit sells before buys if cash needs to be released first.

A close-derived signal fills at the following recorded open with configured adverse slippage and fees. Price gaps therefore affect fills and risk acceptance. Equity caps are checked after the candidate fill using open marks and costs. Price drift afterward may exceed an entry cap. The engine does not inspect that next bar's close/high/low/volume to choose the fill. Full fills assume sufficient liquidity; observed OHLCV alone does not establish that assumption. Final pending orders expire without a fabricated fill, and open positions remain marked at the final close.

## Generate from a Reddit source

```sh
# Actual imported post(s), matching config and exact-universe market files:
python3 -m uv run rsl generate-code data/posts.json --config strategy-config.json \
  --max-model-calls 6 --prices data/basket

# A disclosed interpretation of missing details:
python3 -m uv run rsl generate-code data/posts.json --config hypothesis-config.json \
  --hypotheses --max-model-calls 6 --prices data/basket
```

Without `--prices`, generation stops at reviewed code artifacts. With it, each accepted candidate enters the isolated runner automatically. Both manual URL imports and `discover --collect-only` outputs feed this command. `link`, `discover`, `import` and `extract` also accept `--code-config` and route directly through the custom-code generator; their default provider in that mode is Codex. The original expression path continues when `--code-config` is omitted. Discovery still requires approved Reddit access. Each candidate must match the configured universe and timeframe; incompatible candidates fail instead of adopting a proxy.

Configuration uses the fields illustrated in `examples/custom-code/config.json`. Faithful generation requires `formulation='source_interpretation'` and sufficient source detail. Hypothesis generation requires `formulation='llm_hypothesis'`, `--hypotheses` and explicit assumptions. An intentional close-to-next-open timing change additionally requires `execution_shift='close_to_next_open'`; that is a different strategy interpretation, never an exact replication. Unsupported FX/stops cannot be authorized by this timing option.

The installed Codex CLI extracts native requirements, writes a Python module, then performs a separate source/SDK review. It uses the existing local ChatGPT sign-in and configured model in an ephemeral read-only workspace with nonessential tools disabled and structured JSON output. CLI usage limits still apply and provider failures stop the candidate. Source text is untrusted; no prices or performance go to model calls. Source extraction, generation, review and repairs consume the shared call budget (six calls by default). A rejected semantic review may trigger one code repair and a fresh review if two calls remain. This repair receives only the source, SDK and correctness issues, never returns or prices. Native source extraction may make one schema repair. There is no performance-driven repair loop. Failed requests/candidates remain recorded in ignored local artifacts. Model review can miss errors; it is not mathematical proof of fidelity. Syntax parsing never runs generated code on the host.

Generated folders contain exact code, finalized assumptions/config, raw request/response receipts and model provenance. `run-code` checks code/config hashes against adjacent generated metadata, rejecting changed artifacts. All scored runs snapshot code/config, data and engine hashes before simulation and append start/completion/failure records to `trials.jsonl`. Failed runs withhold performance; source snapshots and a failure record remain for inspection. Local read-only files/checksums are audit aids, not tamper-proof external storage.

The selected provider and model, command receipt and structured responses are retained locally with each generated candidate. Because the CLI executes as a separate authenticated Codex session, it consumes that account's usage allocation. Native Reddit text is untrusted input; a provider's semantic review can still miss mistakes.

## Isolation and checks

The implemented backend uses macOS Seatbelt (`sandbox-exec`), a separately launched Python interpreter, a cleared environment and bounded JSON pipes. It grants system/runtime reads but denies private file contents, file writes, network and process creation. Filesystem metadata remains readable for Python startup. It does not load the host virtualenv or inherit the credential file/key. Standard-library imports are available; third-party packages are not part of this backend.

Before each CLI run, harmless real OS probes verify denied read/write/network/fork operations and absence of credential environment variables. An unavailable or failing sandbox blocks execution, with no unsandboxed fallback. The probe uses a temporary text sentinel, not fabricated market data. The worker has a 30-second total CPU hard limit, per-message deadlines, a 300-second run wall limit, bounded source/input/output and file-descriptor limits. macOS does not provide the desired reliable address-space hard limit here: RSS above 512 MiB is sampled and killed as a **best-effort** guard. This cannot prevent every transient allocation spike. This is a local research backend, not a hardened multi-tenant service. A Linux VM/container backend with hard memory quotas remains a future deployment improvement.

Each successful CLI run replays the first half of the same actual observations in a fresh worker. Inputs and commands must match the corresponding prefix of the full run or performance is withheld. Unit/integration tests additionally check denied private file reads, timeouts, output flooding, invalid commands, next-open timing, accounting, warmup, caps, terminal expiration and repeatability using actual cached market data. Missing real data causes explicit test skips; no invented replacement is generated.

A prefix check cannot detect an embedded table of historical trades or all model memorization. Review the code and assumptions. These runs are labeled retrospective research, with no sealed holdout claim. The trial ledger and absence of performance feedback reduce opportunities for hidden tuning but do not eliminate overfitting or the original author's selection bias. A full locked holdout/forward-evaluation service, quote-driven execution, and additional asset-class adapters are not implemented by this release.

See [the broader architecture](custom-strategy-architecture.md) for remaining stages and primary research sources.
