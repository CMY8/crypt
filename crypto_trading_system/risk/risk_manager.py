"""Risk guardrails for trade signals."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple

from .portfolio_manager import PortfolioManager


@dataclass
class RiskLimits:
    max_position_pct: float = 0.05
    max_daily_loss_pct: float = 0.02
    max_positions: int = 10


class RiskManager:
    def __init__(self, portfolio: PortfolioManager, limits: RiskLimits | None = None) -> None:
        self.portfolio = portfolio
        self.limits = limits or RiskLimits()
        self._starting_equity: float | None = None

    def reset_day(self, starting_equity: float) -> None:
        self._starting_equity = starting_equity

    def validate_signal(self, signal, marks: Dict[str, float], equity: float) -> Tuple[bool, str]:
        price = marks.get(signal.symbol)
        if price is None:
            return False, 'Missing mark price'

        target_notional = abs(signal.quantity) * price
        max_notional = equity * self.limits.max_position_pct
        if target_notional > max_notional:
            return False, 'Position size exceeds risk limit'

        if signal.symbol not in self.portfolio.positions and len(self.portfolio.positions) >= self.limits.max_positions:
            return False, 'Maximum concurrent positions reached'

        if self._starting_equity is not None:
            drawdown = 1 - equity / self._starting_equity
            if drawdown > self.limits.max_daily_loss_pct:
                return False, 'Daily loss limit breached'

        return True, 'OK'


__all__ = ['RiskLimits', 'RiskManager']
