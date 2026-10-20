# Custom strategy code with trusted execution

Research and target architecture, 2026-10-18. A first [custom-code runner](custom-code.md) is now implemented using native macOS isolation and host-owned cash-equity next-open accounting. The VM-backed sandbox, quote-driven adapter and sealed evaluation service below remain proposed. This document distinguishes the target from the narrower released backend.

## Decision

Allow the selected model to produce a complete, individual Python strategy module: functions, classes, custom indicators, state machines and cross-asset calculations. Give that module a small event/command interface. Keep market data delivery, order validation, matching, accounting and evaluation outside its process. The implemented local path uses the installed Codex CLI.

Use a trusted adapter around NautilusTrader as the first candidate for quote-driven execution. Keep the existing cash-equity next-open engine as a regression reference and supported legacy path. Do not replace it blindly: Nautilus bar execution has materially different timing semantics. Confirm the chosen released package version against recorded event replays before adopting it. This is a reasoned recommendation from documentation, not a completed package benchmark.

“Any strategy” means extensible computations over supported observations and order types. It cannot mean accurate simulation of any market with whatever data happens to be available. New execution mechanisms require reviewed engine capabilities; the LLM must never supply its own fill model to get around a missing capability.

## Interface: algorithms are unrestricted in shape, authority is restricted

The following is an interface sketch, not an executable SDK:

```python
class Strategy:
    def initialize(self, config, instrument_metadata): ...
    def on_event(self, event, portfolio_snapshot):
        # Arbitrary custom computation and persistent private state.
        # Return zero or more typed commands; no fills or performance values.
        return commands
```

Host events include completed bars, recorded quotes/trades, scheduled times, as-of universe changes, corporate actions, order acknowledgments/rejections, partial fills and cancellations. Strategies may maintain their own rolling histories from events. A bounded history service, if added, returns only records already released by the host. No full DataFrame or host engine object enters the worker.

Commands include submit, cancel, replace and timer requests. Submission carries a client ID, instrument ID, side, quantity, market/limit/stop/stop-limit type, applicable price levels, time-in-force, expiry and explicit parent/link policy. Price and quantity use instrument increments and decimal wire values. A stop price is an instruction, never a promised fill price. Brackets must declare whether distances reference signal prices or actual fills; partial-fill protection and OCO behavior require explicit semantics. Paired buy/sell stops do not automatically imply OCO.

The host stamps decisions and checks every command against declared capabilities, account limits, pending-order exposure, supported instruments and protocol limits. It owns the authoritative portfolio. Stale account versions, repeated command IDs, malformed/nonfinite values, backdated commands and commands exceeding budgets fail with logged reasons. Cancellation is a request: the strategy learns whether it succeeded from the engine event. Arbitrary code may compute its own estimates, but those never become authoritative results.

## Causality and timing

Every observation needs event time, availability time, source sequence and provenance. Dispatch order follows availability, with a documented deterministic tie policy. A complete hourly candle becomes available after its interval closes. Revised fundamentals/news enter only when the revision was available, not at the original economic period's date. Cross-sectional calculations use the constituents and observations known at the decision time; missing assets do not silently disappear from the universe.

The engine first handles eligible resting orders, then releases observations, then accepts new commands with a strictly later eligibility sequence and configured latency. New commands must not trade against a consumed event. The adapter must enforce this ordering even if a backend allows zero-latency same-cycle settlement. Historical warmup can initialize indicators but cannot submit trades. Fold boundaries reset portfolios and learned state according to the frozen evaluation protocol, with any allowed carryover explicitly recorded.

For a pre-close momentum strategy, the timer arrives before the venue's actual session close, including early closes. It can inspect only quotes and completed bars already available, then submit an order eligible for subsequent real observations. The next morning's exit uses recorded opening-session observations. Using the final daily close to buy before that same close is invalid.

As a causality regression, rerun a recorded real-data prefix in a fresh worker and compare its commands/state hashes with the same prefix of a longer run. They must match. This detects certain leaks and reset errors; it does not prove that all arbitrary programs are causal or free of embedded historical knowledge.

## Isolation

Custom Python must run outside the trusted engine, in a disposable Linux sandbox inside a VM on this Mac; a hardened gVisor worker is another deployment option on supported Linux infrastructure. Do not expose the project directory, full historical dataset, credentials, network, Docker socket, engine internals or prior reports. Transfer bounded serialized events and commands only. Use a fixed dependency image, read-only runtime, unprivileged user, ephemeral storage, CPU/memory/process/output limits, callback deadlines and whole-run deadlines. Missing isolation must disable code execution, not fall back to local exec.

The Codex CLI remains on the trusted host and owns its sign-in. Installation/build steps also require isolation: generated package installation scripts are code. Initial workers use a reviewed, pinned numerical dependency set; additional packages are a capability change, not a strategy instruction.

AST checks and import policies improve diagnostics, but cannot secure general Python. RestrictedPython explicitly says it is not a sandbox. A plain subprocess is also insufficient. Wasmtime is an alternative for a compiled guest with narrowly defined imports, memory and fuel limits; it is less convenient for ordinary Python scientific packages. Prefer Python isolation initially and retain a language-neutral wire protocol. Neither option is a claim of perfect security.

## Real observations only

Never invent prices, interpolate missing ticks, generate pseudo-ticks from OHLC, forward-fill gaps into tradable quotes, or use random market paths. Aggregating recorded ticks into completed bars is an auditable transformation, not fabrication; preserve constituent provenance and gap flags. Orders and fills remain simulated outcomes over real observations, with execution assumptions disclosed.

Nautilus explicitly documents synthetic OHLC market updates for bar matching. Disable that execution path for the proposed strict quote-based backend. Bars may still be supplied as signals derived from real data. Validate the adapter with the exact pinned release; a setting alone does not establish correct timing. The existing next-open equity engine remains a separate disclosed bar approximation, not an intrabar simulator.

Real quotes do not establish actual queue position, executable size or the market impact of our hypothetical orders. Record quote age, liquidity assumptions, latency, fees, spread, financing, margin and borrow restrictions. Fail or label execution uncertainty when the required evidence is absent. Do not call top-of-book FX quotes a full order book.

Dukascopy documents historical tick access and is a candidate FX source, subject to access/terms/coverage verification. Its quotes would represent that provider, not necessarily the Reddit author's MT5 broker. No FX dataset was downloaded or certified as part of this research.

## Model workflow and source fidelity

Both URL and discovery workflows converge on the same pipeline:

1. Version the actual source body and scope. Extract native requirements before selecting a backend.
2. Preserve unknown parameters. In faithful mode, critical gaps remain unresolved. In explicit hypothesis mode, choose and freeze one disclosed interpretation before results.
3. Give the selected model the source contract, SDK, supported capabilities and fixed dependency list. Generate source code, parameter definitions, state transitions and a source-to-code explanation. Do not provide market outcomes or holdout files.
4. Run structural review and an independent semantic comparison to the source. Check omitted exits, inverted inequalities, timeframes, universes, sizing and cancellation policies. Another LLM's agreement is supporting evidence, not proof.
5. Repair syntax/runtime/interface errors under a fixed attempt budget. Repairs see minimized diagnostics, not returns, P&L, full event histories or holdout failures containing outcomes. Freeze code, dependencies and assumptions before scored evaluation.
6. Route typed commands through the trusted engine, then generate reports exclusively from its ledger. Store all attempts, including rejected and failed ones.

For the EUR/USD post: custom code can maintain ATR history, compute its own rolling percentile, arm during compression, detect expansion and submit both pending stops with the stated 0.2/1/2 ATR distances. The code interface removes the expression-language limitation. It does not reveal the missing ATR settings, compression/expansion thresholds, reference price, expiry, sizing or cancellation policy. Those remain required settings or explicitly labeled hypothesis choices. Keep FX netting versus hedging behavior explicit.

## Overfitting is a separate problem

Preventing future file access cannot prevent selecting a strategy because it happened to perform well. The post author may already have selected it on the same historical period; the LLM may have learned historical outcomes during training. Historical tests before the post are retrospective diagnostics, not clean prospective evidence. Unknown post dates or model training coverage prevent strong unseen-data claims.

Create an append-only experiment registry before evaluation. Record source families, code and configuration hashes, prompts/models, all compile/repair attempts, all scored variants, data hashes, split boundaries, costs, stopping rules and selection criteria. Count actual scored trials separately from repairs, while retaining both. A local hash chain detects some changes but is not a tamper-proof external registry.

Use chronological development, validation and sealed final evaluation. Fit scalers/models/universe selectors using eligible training data only. Purge training examples whose label intervals overlap evaluation; choose separation from actual information/holding horizons, not a universal arbitrary number of days. If parameters are tuned, use nested chronological selection. Limit candidate counts and predeclare sensitivity checks. Opening a holdout consumes it for that experiment family; further changes require new evaluation data. New forward observations provide the strongest available check against historical selection and model memorization.

Report every candidate, costs, exposure, drawdown, turnover, trade counts, subperiod results and matched baselines. Deflated Sharpe and probability-of-backtest-overfitting diagnostics can help assess selection under their assumptions; do not report them without adequate trial/return data, and do not treat them as guarantees. They do not remove unknown trials by the Reddit author or LLM. No synthetic resampling is necessary for the initial protocol: use actual chronological observations and label sample limitations.

## Implementation sequence and release gates

| Stage | Change | Required evidence before enabling |
|---|---|---|
| 1 | Versioned event/command protocol, worker lifecycle and isolation | Denied host files/network; bounded loops/output; deterministic restart; malformed commands rejected |
| 2 | Codex code artifacts and source mapping | Exact source/capability preservation; disclosed gaps; bounded repairs; frozen code hashes |
| 3 | Trusted quote-driven backend adapter | Real recorded replay: bid/ask sides, gaps, eligibility, partial fills, expiry, cancellation races, bracket activation, margin and accounting |
| 4 | Trial registry and chronological evaluation | Holdout inaccessible to generator; no training overlap; all trials retained; replay reproduces ledger |
| 5 | Both workflows route to eligible backends | End-to-end real post and real data; unsupported capabilities reported; no silent substitutions |

Existing data-dependent tests and reports remain historical regression artifacts. New tests should use recorded real event slices and protocol/accounting assertions; do not fabricate market datasets to meet coverage. Failures stop that run with its audit intact. The new code mode is ready only after these gates, not after adding an on_event method.

## Sources checked

- [Nautilus strategies](https://nautilustrader.io/docs/latest/concepts/strategies/): event callbacks, state and order handling.
- [Nautilus execution flow](https://nautilustrader.io/docs/latest/concepts/backtesting/execution-flow/): matching/callback/settlement order, including same-cycle commands.
- [Nautilus bar execution](https://nautilustrader.io/docs/latest/concepts/backtesting/bar-execution/): synthetic intrabar updates and timing limitations.
- [QuantConnect algorithm engine](https://www.quantconnect.com/docs/v2/writing-algorithms/key-concepts/algorithm-engine): time-streamed algorithm data model.
- [RestrictedPython](https://restrictedpython.readthedocs.io/en/stable/index.html): explicitly not a sandbox.
- [gVisor security](https://gvisor.dev/docs/architecture_guide/intro/): isolation boundary and resources still exposed by configuration.
- [Wasmtime security](https://docs.wasmtime.dev/security.html): sandbox and capability-based host access.
- [Dukascopy historical interface](https://www.dukascopy.com/swiss/docs/interfaces/IHistory.htm): historical tick API.
- [Bailey et al., Probability of Backtest Overfitting](https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf).
- [Bailey and López de Prado, Deflated Sharpe Ratio](https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf).

The architecture, protocol choices and acceptance gates above are this project's recommendations. Documentation reviewed here does not establish that this proposed integration has passed them.
