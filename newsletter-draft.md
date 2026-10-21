# i built a bot that makes reddit trading strategies show their work

*it finds strategy posts, turns the testable ones into backtests, and calls out the ones that leave half the rules in somebody’s head.*

![Blue banner with the Reddit logo pointing toward a question-marked money goal](assets/reddit-strategy-finder-cover.png)

## the idea

there’s always someone on a trading subreddit posting a chart with a caption like “this setup prints.” the replies are already split between “genius” and “this is overfit.” somewhere in there is a question nobody has time to answer: what did they actually test?

i wanted a way to check the idea without copying the post into a notebook, guessing what the rules mean, then writing a new backtester every time. i want the post, the rules the system pulled from it, the code, and what happened when those rules met real prices. otherwise i’m just larping as a quant because a line went up.

the main reason i built it is i don’t have all the time in the world. i’ve got school, homework, other projects, and i still want to test more than one idea every few weeks. so the system can search a batch of posts, turn the ones with enough detail into rules, run the backtests, and leave the reports for me to review. i can spend my time checking what it did instead of manually feeding every post through the same steps.

i’m Vihaan, a high-school freshman trying to make $1 million trading before i graduate. i have about $900 in my account, so yeah, plenty of room between here and there. this project is one way to get better at finding and testing ideas. it searches Reddit strategy posts, tries to turn them into rules, and sends those rules through a backtest. if a post leaves out something important, the system should say so instead of inventing a rule and calling it alpha.

the flow has two possible endings:

> **testable:** enough detail → rule sheet → Python strategy → backtest → report
>
> **not testable yet:** missing detail → flag the gap → no made-up backtest

that second path is the feature i care about most. “i can’t test this yet” is a much better answer than a clean-looking result based on a guess.

i put the code, configs and example reports on [GitHub](https://github.com/V-Juneja/reddit-strategy-lab) so you can check what it did. the reports include the rules it tested, which matter a lot more than a cropped screenshot of the profitable bit.

---

## 1. finding posts without reading all of reddit

the scanner checks selected subreddits through Reddit’s OAuth access. it looks at new, hot and top posts, plus searches for words like momentum, volatility, entries and exits. each run has a request limit, and it rotates which feed it checks first so one busy subreddit doesn’t eat the whole budget. if access is missing, it stops. no sneaky anonymous scraping.

for each post, it saves where it found it, when it found it, and a fingerprint of the text. if the same post shows up in a few feeds, it gets marked as a duplicate. saved cursors let the next run pick up where the last one stopped.

there’s a collect-only mode too. it saves the posts and search log without calling the model or running a backtest. useful when i want to see whether the scanner found actual rules or 40 variations of “trust me bro.”

this is a bounded scan of selected feeds, not every Reddit post ever made. it reads the post, not its comments or linked articles. so if the actual entry rule is hiding in a comment, the scanner misses it. when a post doesn’t give enough detail, the result should be “needs clarification” or “unsupported,” not a confident chart based on rules nobody wrote.

---

## 2. turning “buy the dip” into actual rules

posts are written for people, not code. “buy the dip and sell when it turns around” sounds like a strategy until you ask what counts as a dip.

before it writes anything, the system checks the symbol, timeframe, entry, exit, position sizing, and what the post leaves ambiguous. those aren’t little details. change the fill time or the exit rule and you’ve changed the strategy.

a language model turns the post into a rule sheet, with short quotes showing where each rule came from. the system checks that sheet against a fixed schema and the data config. if the post leaves out a required detail, faithful mode stops. if the backtester doesn’t support the market or order type, it records that instead of swapping in SPY just to get a chart.

there’s also a hypothesis mode for testing an interpretation. any assumption has to show up beside the result, so nobody mistakes my version for what the Reddit author actually said.

“two red days” is a good example. does that mean two candles that closed below their open, or two closes lower than the day before? those are different signals. if the code quietly picks one, the backtest answers a question the post never asked.

---

## 3. getting the code to follow the post

once a post has enough detail, the coding model gets the post, its rule sheet, and a small interface that tells it what the strategy can do. it writes a Python strategy from those rules. it doesn’t see the historical prices or backtest results while writing. that keeps this run from turning into an optimization loop where the model sees a bad result and quietly edits the rules until the chart looks nicer.

i use the Codex CLI i’m already signed into. i was not about to spend a pile of money on model credits just to find out “buy the dip” doesn’t compile. the repo doesn’t store a model API key.

the generated code can look at completed bars and the simulated account’s cash and positions. it can ask to place an order, but it can’t decide the order filled, pick its own price, or edit the account balance. a separate check compares the code to the rule sheet and checks that it uses the interface properly. if it finds a specific problem, the model gets one try to fix it. if that still fails, there’s no result to publish.

a clean-looking Python file doesn’t prove the model understood the post. the report keeps the source, rule sheet, assumptions, code and review result together so you can see exactly where my test might have drifted from the original claim.

---

## 4. the backtester handles the money part

the strategy can ask for an order. the backtest engine handles prices, fills and the account.

it needs actual price files for the exact symbol and timeframe in the config. it checks for missing or misaligned bars instead of filling gaps with made-up prices or quietly switching tickers. the strategy only sees completed bars, so a signal at today’s close can first trade at tomorrow’s open. trading at the close after using that same close to make the decision would sneak in information you didn’t have yet. quants call that look-ahead bias; i call it accidentally inventing a time machine.

the engine checks each order against cash and position limits. it handles whole shares, fees and slippage, rejects buys the account can’t afford, and rejects sells that would create a short position. slippage is the small price penalty you pay when the fill isn’t as good as the price on your screen. it’s small per trade and pretty annoying once a strategy keeps trading. no magic fill at the same close that triggered the signal.

the generated code also runs in a restricted macOS sandbox. it can’t read project files or credentials, use the network, or launch another process. it gets a limited snapshot of the market and account, then returns typed order requests. if the sandbox check fails, the run stops.

---

## 5. one post goes through the pipeline

every candidate gets a status: ran, needs more detail, unsupported, or skipped. if it runs, the report saves the original post, extracted rules, code, settings, orders and charts together. a green line by itself doesn’t tell you what the system thought it was testing.

one post described buying SPY after two consecutive lower closes and holding for five sessions. the system turned that into rules and ran it through the same engine. for this example, it used daily SPY prices from 2020 to 2024, a simulated $10,000 account, next-open fills, whole shares, and fees and slippage on every fill. those settings are frozen in the [case report](examples/reports/post-1x8o01e/report.md). dividends are excluded.

![Matplotlib comparison of the Reddit-sourced rule and SPY buy-and-hold, starting from $10,000](examples/reports/post-1x8o01e/article-equity-vs-spy.png)

*the same starting cash and window. the orange line is the Reddit rule; the comparison is SPY buy-and-hold.*

the rule finished up about 62% over the five-year window. i stared at that chart for a second. then i put SPY buy-and-hold beside it: up about 79% over the same window. i got beat by buying the thing and doing nothing.

*me seeing +62% before scrolling down to the SPY line:*

![Martin Scorsese “Absolute Cinema” reaction GIF](https://media1.tenor.com/m/Y8KOj1DPatQAAAAd/martin-scorsese-absolute-cinema.gif)

[GIF via Tenor](https://tenor.com/view/martin-scorsese-absolute-cinema-absolute-cinema-meme-martin-scorsese-meme-martin-scorsese-absolute-cinema-gif-7188464701423971028)

![Matplotlib drawdown comparison for the Reddit-sourced rule and SPY buy-and-hold](examples/reports/post-1x8o01e/article-drawdown-vs-spy.png)

*the return lost to SPY, but the deepest drop was smaller. that’s the part the first chart can’t show.*

there is a wrinkle, though. max drawdown, the biggest peak-to-trough drop, was about 18% for the rule versus 33% for buy-and-hold. so it made less money here, but took a smaller hit along the way. that’s why i care about risk-adjusted performance, not just the final equity number. Sharpe ratio is one way to put return next to volatility, but one neat ratio wouldn’t settle this either. exposure matters: a strategy sitting in cash for part of the test is taking different risk from owning SPY the whole time.

also, this post came *after* the price window. the backtest is retrospective, not an untouched out-of-sample test. i can inspect how the system translated the rule and whether the trades line up; i can’t claim this chart predicts what happens next.

another post gave the bot a “red Monday, buy Tuesday, sell Wednesday” rule. the first generated version refused to trade because it couldn’t tell whether those weekdays were both market sessions in a holiday week. honestly, fair. i had to give the strategy the upcoming exchange-session dates before the test could run. the [second case report](examples/reports/post-1wmxzw7/report.md) is in the repo too. i like that this failure showed up as a missing input instead of a mysterious zero-trade chart.

---

## 6. keep it running while i work on other stuff

right now, i run the finder in bounded batches. once it starts, it processes eligible posts and leaves reports for me to review. it saves its place too. i haven’t put it on a scheduler yet, but that’s the idea: let it keep looking while i’m at school or working on something else, then come back to a stack of candidates and rejections instead of another hour of scrolling.

if something looks interesting, i can check the original post, see how the system translated it, and paper-test it. only after that would i consider testing it in my separate live algo-trading setup. the Reddit finder itself can’t place trades.

---

## 7. the part where i try not to fool myself

automating the steps doesn’t mean the results are automatically good. a post can be wrong, edited or missing context. the model can misunderstand a rule. a strategy can look good by luck. and a backtest can miss real stuff like market impact, queue position or delayed prices.

this pilot uses one fixed SPY price window and a small number of examples. the posts themselves came later than that window, which means selection bias is a real problem: whoever wrote them may have already seen what worked in those years. then there’s multiple testing. scan enough ideas and some will look great by luck alone. i want to keep the candidates that fail too. otherwise the newsletter turns into a museum of surviving charts.

i keep seeing people post one good-looking backtest and act like they found the next Medallion Fund. maybe somebody did find something interesting. i’d still like to see the entry rule, the fill assumptions, the drawdown, and what happens next to a benchmark before we start naming the fund.

the goal is still $1 million before i graduate. right now i’ve got about $900, a bot that reads Reddit strategy posts, and a first chart that looked amazing until i put SPY on the same axes. i’m going to keep trying ideas, including the ones i find myself, and show the work even when the benchmark wins.

subscribe to **Probably Overfit** if you want to follow the attempt. i post twice a week: what i tested, what broke, and whether any of this gets me closer to the million or just better at spotting my own larping.

![The road to $1 million: $900 of $1,000,000, or 0.09%](assets/road-to-1m-900.png)
