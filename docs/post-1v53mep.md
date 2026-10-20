# Audit of the requested EUR/USD strategy

Source: [What do u think about my strategy?](https://www.reddit.com/r/algotrading/comments/1v53mep/what_do_u_think_about_my_strategy/). Publication timestamp is unavailable in the accessible page representation and is stored as unknown, not guessed. Only the main post body was used; comments, linked reports and reported returns were not used to formulate rules.

The current Codex source-contract workflow is designed to preserve these source requirements before any executable translation. No performance backtest or FX-price substitution was performed:

- EURUSD, one-hour bars.
- ATR low-percentile comparison against the previous 500 ATR observations.
- Low-volatility arming followed by sharp ATR expansion, while retaining unresolved timing semantics.
- Both a buy-stop and a sell-stop, each 0.2 ATR from an unspecified reference.
- Each order has a 1 ATR stop loss and 2 ATR profit target.

ATR period/smoothing, percentile threshold, expansion definition, reference price, ATR snapshot timing, expiry, opposite-order cancellation, sizing, spread/commission and financing remain unknown. Whether the ATR must still be in its low percentile on the expansion bar and how long the armed state persists also need clarification. No default values were selected.

The cash-equity engine does not implement spot-FX calendars/bid-ask execution, shorts, paired pending entry stops or intrabar stop/target ordering. Source-native capability checks now run BEFORE executable translation, including cached executable interpretations. Independent source-text checks detect explicit FX instruments, dual stops, ATR offsets and changed timeframes; model claims alone cannot enable an unsupported capability. Source-native contracts are descriptive JSON and never executable Python.

The guarded CLI returns unsupported. It does not show a SPY/QQQ proxy, market-order approximation, synthetic price series, profit factor or Sharpe for this post. Reproducing the author's performance requires their EA/source or exact settings plus real bid/ask or tick history and a verified FX stop/bracket simulator. Even hourly OHLC cannot uniquely identify which of two entry/exit levels fired first within a bar.

```sh
python3 -m uv run rsl inspect data/posts/1v53mep.json --out runs/post-1v53mep/source-audit --max-model-calls 2
```

The audit blocks execution before an unsupported stock proxy can be created. Raw post/model responses remain ignored locally.
