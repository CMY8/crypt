"""Simple grid strategy stub."""

from __future__ import annotations

from typing import Dict, Iterable, List

from .base_strategy import BaseStrategy, Signal


class GridStrategy(BaseStrategy):
    def __init__(self, name: str, settings, levels: int = 5, spacing: float = 0.01) -> None:
        super().__init__(name, settings)
        self.levels = levels
        self.spacing = spacing
        self._anchors: Dict[str, float] = {}

    async def generate_signals(self, payload: Dict[str, float]) -> Iterable[Signal]:
        symbol = payload['symbol']
        price = payload['price']
        anchor = self._anchors.setdefault(symbol, price)
        signals: List[Signal] = []
        for level in range(1, self.levels + 1):
            buy_level = anchor * (1 - self.spacing * level)
            sell_level = anchor * (1 + self.spacing * level)
            if price <= buy_level:
                signals.append(Signal(symbol=symbol, side='BUY', quantity=1.0, confidence=1.0))
                self._anchors[symbol] = price
                break
            if price >= sell_level:
                signals.append(Signal(symbol=symbol, side='SELL', quantity=1.0, confidence=1.0))
                self._anchors[symbol] = price
                break
        return signals


__all__ = ['GridStrategy']
