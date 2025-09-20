"""Example momentum strategy."""

from __future__ import annotations

from collections import deque
from statistics import mean
from typing import Deque, Dict, Iterable

from .base_strategy import BaseStrategy, Signal


class MomentumStrategy(BaseStrategy):
    def __init__(self, name: str, settings, window: int = 5, threshold: float = 0.002) -> None:
        super().__init__(name, settings)
        self.window = window
        self.threshold = threshold
        self._prices: Dict[str, Deque[float]] = {}

    async def generate_signals(self, payload: Dict[str, float]) -> Iterable[Signal]:
        symbol = payload['symbol']
        price = payload['price']
        history = self._prices.setdefault(symbol, deque(maxlen=self.window))
        history.append(price)
        if len(history) < self.window:
            return []
        avg = mean(history)
        delta = (price - avg) / avg
        if delta > self.threshold:
            return [Signal(symbol=symbol, side='BUY', quantity=1.0, confidence=float(delta))]
        if delta < -self.threshold:
            return [Signal(symbol=symbol, side='SELL', quantity=1.0, confidence=float(-delta))]
        return []


__all__ = ['MomentumStrategy']
