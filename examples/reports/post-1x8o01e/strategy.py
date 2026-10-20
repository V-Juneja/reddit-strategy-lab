import math
from datetime import date


class Strategy:
    def __init__(self, parameters: dict):
        self.symbol = 'SPY'
        self.hold_sessions = int(parameters.get('hold_sessions', 5))
        self.fraction = float(parameters.get('fraction', 1.0))
        if self.hold_sessions < 1:
            raise ValueError('hold_sessions must be positive')
        if not math.isfinite(self.fraction) or not 0 < self.fraction <= 1:
            raise ValueError('fraction must be in (0, 1]')
        self.previous_close = None
        self.down_streak = 0
        self.last_session = None
        self.held_sessions = 0
        self.command_number = 0

    def _command(self, side, quantity):
        self.command_number += 1
        return {
            'id': 'spy_two_down_' + str(self.command_number),
            'symbol': self.symbol,
            'side': side,
            'quantity': int(quantity),
            'type': 'market',
            'valid_for': 'next_bar',
        }

    def on_event(self, event: dict, portfolio: dict) -> list[dict]:
        if event.get('kind') != 'bar_close':
            return []
        bar = event.get('bars', {}).get(self.symbol)
        if not bar:
            return []
        session = bar.get('session') or event.get('session')
        if not isinstance(session, str):
            return []
        try:
            date.fromisoformat(session)
            close = float(bar['close'])
        except (KeyError, TypeError, ValueError, OverflowError):
            return []
        if not math.isfinite(close) or close <= 0:
            return []
        if self.last_session is not None and session <= self.last_session:
            return []
        self.last_session = session

        if self.previous_close is not None and close < self.previous_close:
            self.down_streak += 1
        else:
            self.down_streak = 0
        self.previous_close = close

        quantity = int(portfolio.get('positions', {}).get(self.symbol, 0))
        if quantity > 0:
            self.held_sessions += 1
        else:
            self.held_sessions = 0

        if event.get('warmup', False):
            return []

        # Actual ownership includes fills at this session's open. Consequently
        # that session counts immediately, including for a one-session hold.
        if quantity > 0:
            if self.held_sessions >= self.hold_sessions:
                return [self._command('sell', quantity)]
            return []

        if self.down_streak < 2:
            return []
        try:
            cash = float(portfolio.get('cash', 0.0))
            equity = float(portfolio.get('equity', 0.0))
        except (TypeError, ValueError, OverflowError):
            return []
        if not all(math.isfinite(value) and value > 0 for value in (cash, equity)):
            return []

        # Use the signal close to estimate next-open affordability. The host
        # remains authoritative if the next open makes this order unaffordable.
        estimated_fill = close * (1.0 + 3.0 / 10000.0)
        estimated_cash_per_share = estimated_fill * (1.0 + 2.0 / 10000.0)
        budget = min(cash, equity * self.fraction)
        shares = math.floor(budget / estimated_cash_per_share)
        if shares < 1:
            return []
        return [self._command('buy', shares)]
