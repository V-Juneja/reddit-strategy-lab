"""Engine demonstration, not a Reddit reproduction or a claimed profitable strategy.

Ranks a declared basket with a custom downside-sensitive momentum score.
Uses only the rolling observations delivered to this worker.
"""

import math
from collections import deque


class Strategy:
    def __init__(self, parameters):
        self.window = parameters["window"]
        self.fraction = parameters["fraction"]
        self.history = {}
        self.month = None

    def on_event(self, event, portfolio):
        for symbol, bar in event["bars"].items():
            self.history.setdefault(symbol, deque(maxlen=self.window + 1)).append(bar["close"])
        month = event["session"][:7]
        if (
            event["warmup"]
            or month == self.month
            or any(len(h) <= self.window for h in self.history.values())
        ):
            return []
        self.month = month
        scores = {}
        for symbol, history in self.history.items():
            prices = list(history)
            returns = [b / a - 1 for a, b in zip(prices, prices[1:])]
            downside = math.sqrt(sum(min(r, 0) ** 2 for r in returns) / len(returns))
            scores[symbol] = (prices[-1] / prices[0] - 1) / (downside + 0.0001)
        winner = max(sorted(scores), key=lambda symbol: scores[symbol])
        commands = []
        for symbol, quantity in portfolio["positions"].items():
            if quantity and (symbol != winner or scores[winner] <= 0):
                commands.append(
                    dict(
                        id=f"sell_{event['sequence']}_{symbol}", symbol=symbol, side="sell", quantity=quantity
                    )
                )
        if scores[winner] > 0 and not portfolio["positions"][winner]:
            quantity = int(portfolio["equity"] * self.fraction / event["bars"][winner]["close"])
            if quantity:
                commands.append(
                    dict(id=f"buy_{event['sequence']}_{winner}", symbol=winner, side="buy", quantity=quantity)
                )
        return commands
