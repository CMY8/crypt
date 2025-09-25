"""Portfolio accounting helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict


@dataclass
class Position:
    symbol: str
    quantity: float = 0.0
    average_price: float = 0.0

    def market_value(self, mark_price: float) -> float:
        return self.quantity * mark_price


@dataclass
class PortfolioSnapshot:
    cash: float
    positions: Dict[str, Position] = field(default_factory=dict)

    def equity(self, marks: Dict[str, float]) -> float:
        value = self.cash
        for symbol, position in self.positions.items():
            mark_price = marks.get(symbol, position.average_price)
            value += position.market_value(mark_price)
        return value


class PortfolioManager:
    """Tracks balances and open positions."""

    def __init__(self, starting_cash: float) -> None:
        self._snapshot = PortfolioSnapshot(cash=starting_cash)

    @property
    def cash(self) -> float:
        return self._snapshot.cash

    @property
    def positions(self) -> Dict[str, Position]:
        return self._snapshot.positions

    def update_cash(self, delta: float) -> None:
        self._snapshot.cash += delta

    def update_position(self, symbol: str, fill_quantity: float, fill_price: float) -> Position:
        position = self._snapshot.positions.setdefault(symbol, Position(symbol))
        if fill_quantity == 0:
            return position

        current_qty = position.quantity
        new_quantity = current_qty + fill_quantity

        if new_quantity == 0:
            position.quantity = 0.0
            position.average_price = 0.0
            return position

        if current_qty == 0:
            position.quantity = new_quantity
            position.average_price = fill_price
            return position

        if current_qty * fill_quantity > 0:
            total_size = abs(current_qty) + abs(fill_quantity)
            weighted_price = (
                position.average_price * abs(current_qty) + fill_price * abs(fill_quantity)
            ) / total_size
            position.quantity = new_quantity
            position.average_price = weighted_price
            return position

        # Opposite direction fill (reducing or flipping the position)
        if abs(fill_quantity) < abs(current_qty):
            position.quantity = new_quantity
            # average price unchanged on partial close
            return position

        # Position flipped direction; carry the remainder at the new fill price
        position.quantity = new_quantity
        position.average_price = fill_price
        return position

    def mark_to_market(self, marks: Dict[str, float]) -> float:
        return self._snapshot.equity(marks)


__all__ = ['PortfolioManager', 'PortfolioSnapshot', 'Position']
