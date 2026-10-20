# Methodology and decisions

## Engine and provenance

A narrow deterministic engine was selected after reviewing the reference stockalgo engine and its REVALIDATION_REQUIRED allocation-cap notice. The old optimizer could redistribute weights beyond hard caps; those historical optimizer winners are not evidence for this project. No reference code, credentials, records, datasets, Git history, or live workflow was copied. The reference engine has strategy-specific dependencies and side effects unsuitable for this small independent project. Original project code is MIT; dependencies retain their own licenses. No unresolved reused-code licensing applies because no code was reused.

One shared cash account, explicit US stock/ETF securities, whole shares, no leverage. Budget is min(cash, marked cash equity * entry fraction) including purchase fee and adverse slippage. Allocation is an entry cap; subsequent price changes can increase exposure. No cap redistribution occurs. Borrowing, derivatives and intrabar stops/targets are unsupported. Explicit stock baskets support custom cross-sectional ranking; implicit/dynamic universes and cross-asset benchmark expressions are not represented. Missing capabilities cause exclusion. Closing-price stops can be expressed as next-open exits using entry_price; they are not intrabar stop orders.

## Creativity with boundaries

The paragraphs in this section describe the legacy expression backend. The additional [custom Python backend](custom-code.md) runs generated source only inside its verified OS sandbox and keeps execution/accounting on the host. Its supported mechanics and limitations are documented separately.

Codex writes each strategy as unique Python through the constrained event/command interface rather than choosing a hardcoded RSI template. Strategies may implement causal indicators, state and cross-asset calculations; the host validates code syntax, executes it in an OS sandbox and enforces all fills, accounting and limits.

Faithful mode extracts only sufficiently complete rules and discloses noncritical assumptions. Explicit hypothesis mode can fill missing details or propose a causal interpretation BEFORE results, under the fixed policy documented in README. It must disclose changes and use llm_hypothesis + interpretation labels. It is not reproduction of the original author's backtest. A conservative source-text basket gate also prevents single-symbol execution of plainly described baskets. It does not prove semantic correctness: human source review remains necessary.

## Model boundary

The credential file is read only for the approved Reddit environment names. Neither file paths, credentials nor market returns are provided to Codex. Reddit text is untrusted user content, separate from the system policy. No shell, file, browsing, network tools or brokerage functions are offered. Any returned tool call is rejected. Structured output and Pydantic validation do not prove semantic fidelity. Exact quotes must occur in the source; total quotations are limited to 240 characters per report. An evidence quote cannot establish that the model has interpreted it correctly.

Cache identity includes content hash, provider endpoint, requested model, exact prompt/schema/policy, prompt version and token limit. Actual returned model/response IDs and usage are retained. Up to two schema-only repairs are permitted; every request, including failures and repairs, consumes the configured call budget. No price/results feedback enters repair. Transport failures do not trigger paid retries. Output-token and request caps bound usage, not an exact dollar amount; set provider billing limits independently. All responses, validation failures and attempt metadata stay in ignored local data/model-cache.

## Collection and permissions

Reddit access requirements were checked on 2026-10-18 using the official [Data API Wiki](https://support.reddithelp.com/hc/en-us/articles/16160319875092-Reddit-Data-API-Wiki), [Data API Terms](https://redditinc.com/policies/data-api-terms) and [Responsible Builder Policy](https://support.reddithelp.com/hc/en-us/articles/42728983564564-Responsible-Builder-Policy). Approved access, OAuth and an identifying user agent are required for automated collection. The approval environment flag is an operator assertion, not proof of approval. No anonymous-JSON fallback, proxy bypass, deleted-content recovery or bulk scraper is provided. Revoked/inaccessible content must be deleted locally when required by applicable terms.

The two workflows are a canonical URL lookup and bounded discovery across new/top/hot and topic-search streams. Each stream has its own cursor; round-robin scheduling rotates the first stream between runs to reduce starvation under request caps. Up to three transport attempts respect rate-limit headers; delays above 60 seconds fail for later resumption. Versioned source hashes deduplicate collection. A persisted listing cursor resumes a snapshot; listings are not full historical coverage. On exhaustion a new scan may revisit existing versions, whose cached extraction/run identities avoid treating them as new discoveries. No comments or linked pages are automatically collected.

Manual/public-web imports must record their access method and content scope. A date-only publication is not upgraded to a fabricated exact timestamp. No author identifiers are retained. The pilot uses two public page bodies available during this session, not approved API collection. Raw content stays local; public reports contain links and short excerpts only. No redistribution permission is implied.

## Data and causal fills

Real OHLCV CSVs are cached locally with provider/download/adjustment/dividend/universe disclosures and SHA256. The symbol-specific Yahoo adapter stores original provider JSON too; it uses quote OHLC consistently, never dividend-adjusted close mixed with other prices. It rejects split events needing separate validation, missing observations and symbol substitution. SPY had no split events in the pilot period. Vendor corrections and errors remain possible. Price returns exclude cash dividends; the buy-and-hold comparator uses the same convention. A current surviving ETF is not a point-in-time stock universe.

XNYS calendar handles holidays, early closes and DST. Start/end timestamps are timezone-aware; bars must be complete regular sessions with no missing bars/sessions, ordered OHLC and finite values. Intraday duration must match timeframe. Daily timestamps represent scheduled session boundaries, not fabricated intraday observations. Calendar endpoints do not prove when a vendor published a bar; operational feed latency is unmodeled.

The custom-code callback also supplies the next two scheduled XNYS session **dates**, with no future OHLCV or run-length information. This supports weekday rules that need to skip ordinary holiday weeks. The installed historical calendar may encode extraordinary closures learned only after they happened, so use a point-in-time calendar before claiming strict as-of-time event-calendar causality across such periods.

Only completed bars generate signals. Orders fill next eligible bar open. A pre-close signal may enter only at a later intraday open in the SAME session; it expires at the boundary. Optional overnight exit fills at a later session's first open. No same-close fills. Zero-volume bars cannot fill; an unfilled exit requires the exit condition again (or repeated overnight-exit instruction). No partial fills, queue/auction mechanics or market impact are modeled. A positive-volume bar alone does not guarantee the assumed liquidity.

Position state is snapshotted at each completed bar: bars_held includes entry bar; sessions_held includes entry session; entry_price is the slippage-adjusted purchase price. Rules can use past state, but never future state. End positions remain marked; terminal liquidation is not invented.

## Research design

Before simulating any candidate, a content-addressed manifest freezes every source version, extraction, period boundaries, price/metadata hashes, capital, code hash, runtime, baselines, cost variants and acceptance/evaluation criteria. It is made read-only and checksum-protected. This is local tamper evidence, not a trusted timestamp or cryptographic proof against an operator rewriting files. Final artifact inventories are checked on reuse. Changed rules or code create new attempts instead of replacing runs.

There is no parameter search and no LLM feedback from performance. Every candidate and failure is retained. Family labels flag related candidates but do not reliably detect every semantic duplicate. Source selection, many hypotheses and model training knowledge still create selection bias/multiple testing. No top result is called an edge. Text may have been edited after publication; clean post-publication reproduction is disabled. Development inspected historical prices and outputs; no test period is called untouched. Reserve later truly unobserved data for future evaluation.

Baselines are cash at zero interest and same-symbol buy-and-hold with the same entry cap, costs and dates. Their exposure/risk differ. Planned sensitivity adds 5bps to both fees and slippage without changing rules. Return, bar-mark drawdown, bar-end exposure, closed trades, fills and turnover are deterministic. Sharpe uses session-end returns and 252 sessions/year, sample standard deviation, zero risk-free rate; fewer than 20 sessions or zero volatility yields null. No-trade results remain valid but do not demonstrate efficacy.

## Provider references

The installed Codex CLI owns model authentication and model selection. See the Yahoo provider's own terms before using or redistributing downloaded prices. Its chart interface is not promised stable or available.

## Basket accounting

Explicit universes (at most 50 named securities) require a real file for every symbol and exactly aligned completed-bar timestamps. No intersection, forward fill or substitute ETF is used. Conditions are evaluated per name, and custom formula scores rank eligible candidates using completed data. Stable symbol order breaks ties. Signal mode enters available slots and retains holdings until an exit; session/month modes choose targets using prior session/month observations and rebalance at the next open. Month-end scheduling uses known session dates, never later prices.

Rotation target weight is min(per-position cap, total cap / number selected). It never redistributes unused allocation above a cap. Sells occur before buys; integer-rounded buys include fees and adverse slippage and are constrained by shared cash and current gross limits. Market drift can exceed entry caps between rebalances. An illiquid unsold position is retained rather than assigned a fictitious fill and consumes available cash/capacity. A no-sellable-position case is not proof of realistic liquidity. Rebalance sizing assumes open-price information is available for notional allocation; actual auction order sizing can differ.

Basket partial rebalances produce fills, not an invented number of closed round trips; closed_trades is null for that engine. Every fill carries its actual symbol. Equity, cash, holdings, exposure and turnover are recorded. Equal-weight capped buy-and-hold uses the same universe but can hold a different number of names or risk exposure. A six-name, 10%-cap regression against real observations verifies that at least 40% initial cash remains unallocated.

A normalized strategy-code and configuration signature identifies identical frozen artifacts, though it cannot detect every semantic duplicate. Every discovery candidate remains recorded. The host never rewrites model rules in response to performance.
