from datetime import date, timedelta
from math import floor, isfinite


class Strategy:
    def __init__(self, parameters: dict):
        parameters = parameters or {}
        fraction = float(parameters.get('fraction', 1.0))
        if not isfinite(fraction) or not 0 < fraction <= 1:
            raise ValueError('fraction must be finite and in (0, 1]')
        self.fraction = fraction
        self.symbol = 'SPY'
        self.previous_session = None
        self.previous_close = None
        self.last_session = None
        self.command_number = 0

    def _command(self, side, quantity):
        self.command_number += 1
        return {
            'id': 'turnaround_' + str(self.command_number),
            'symbol': self.symbol,
            'side': side,
            'quantity': int(quantity),
            'type': 'market',
            'valid_for': 'next_bar',
        }

    @staticmethod
    def _date(value):
        try:
            return date.fromisoformat(str(value))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _positive(value):
        try:
            value = float(value)
        except (TypeError, ValueError, OverflowError):
            return None
        return value if isfinite(value) and value > 0 else None

    def on_event(self, event: dict, portfolio: dict) -> list[dict]:
        if event.get('kind') != 'bar_close':
            return []
        bar = event.get('bars', {}).get(self.symbol)
        if not isinstance(bar, dict):
            return []
        session = self._date(event.get('session'))
        close = self._positive(bar.get('close'))
        if session is None or close is None:
            return []
        if bar.get('session') is not None:
            if self._date(bar['session']) != session:
                return []
        if self.last_session is not None and session <= self.last_session:
            return []

        prior_session = self.previous_session
        prior_close = self.previous_close
        self.previous_session = session
        self.previous_close = close
        self.last_session = session

        if event.get('warmup', False):
            return []

        owned = int(portfolio.get('positions', {}).get(self.symbol, 0))
        if owned > 0:
            # A Tuesday-open fill is visible at Tuesday close. Submit
            # its exit now so execution occurs at Wednesday open.
            # If an exit was rejected, actual ownership triggers a retry.
            return [self._command('sell', owned)]

        if session.weekday() != 0:
            return []
        if prior_session != session - timedelta(days=3):
            return []
        if prior_close is None or close >= prior_close:
            return []

        scheduled = event.get('next_sessions', [])
        if not isinstance(scheduled, (list, tuple)) or len(scheduled) < 2:
            return []
        if self._date(scheduled[0]) != session + timedelta(days=1):
            return []
        if self._date(scheduled[1]) != session + timedelta(days=2):
            return []

        cash = self._positive(portfolio.get('cash'))
        equity = self._positive(portfolio.get('equity'))
        if cash is None or equity is None:
            return []
        # Configured costs: 3 bps adverse buy slippage and 2 bps fee.
        # The next opening price is unknown; this is a sizing estimate.
        estimated_fill = close * (1.0 + 3.0 / 10000.0)
        estimated_cash_per_share = estimated_fill * (1.0 + 2.0 / 10000.0)
        budget = min(cash, equity * self.fraction)
        quantity = floor(budget / estimated_cash_per_share)
        if quantity < 1:
            return []
        return [self._command('buy', quantity)]
