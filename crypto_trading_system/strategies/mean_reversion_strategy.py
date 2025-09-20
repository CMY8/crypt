"""Example mean reversion strategy."""

from __future__ import annotations

from collections import deque
from statistics import mean
from typing import Deque, Dict, Iterable

from .base_strategy import BaseStrategy, Signal


class MeanReversionStrategy(BaseStrategy):
    def __init__(self, name: str, settings, window: int = 20, zscore: float = 1.5) -> None:
        super().__init__(name, settings)
        self.window = window
        self.zscore = zscore
        self._prices: Dict[str, Deque[float]] = {}

    async def generate_signals(self, payload: Dict[str, float]) -> Iterable[Signal]:
        symbol = payload['symbol']
        price = payload['price']
        history = self._prices.setdefault(symbol, deque(maxlen=self.window))
        history.append(price)
        if len(history) < self.window:
            return []
        avg = mean(history)
        deviation = max(avg * 0.01, 1e-6)
        z_value = (price - avg) / deviation
        if z_value > self.zscore:
            return [Signal(symbol=symbol, side='SELL', quantity=1.0, confidence=float(z_value))]
        if z_value < -self.zscore:
            return [Signal(symbol=symbol, side='BUY', quantity=1.0, confidence=float(-z_value))]
        return []


__all__ = ['MeanReversionStrategy']
