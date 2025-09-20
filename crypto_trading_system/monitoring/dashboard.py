"""Dashboard data aggregation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict

from ..risk import PortfolioManager


@dataclass
class DashboardState:
    portfolio: PortfolioManager
    marks: Dict[str, float] = field(default_factory=dict)

    def portfolio_summary(self) -> Dict[str, object]:
        equity = self.portfolio.mark_to_market(self.marks)
        cash = self.portfolio.cash
        locked = max(equity - cash, 0.0)
        assets: Dict[str, Dict[str, float]] = {}
        unrealized = 0.0
        for symbol, position in self.portfolio.positions.items():
            mark_price = self.marks.get(symbol, position.average_price)
            market_value = position.market_value(mark_price)
            assets[symbol] = {
                'quantity': position.quantity,
                'average_price': position.average_price,
                'market_value': market_value,
            }
            unrealized += (mark_price - position.average_price) * position.quantity
        return {
            'total_balance': equity,
            'available_balance': cash,
            'locked_balance': locked,
            'daily_pnl': 0.0,
            'unrealized_pnl': unrealized,
            'assets': assets,
        }

    def update_mark(self, symbol: str, price: float) -> None:
        self.marks[symbol] = price


__all__ = ['DashboardState']
