"""Offline simulation harness for strategies."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import List

from ..risk import PortfolioManager, RiskManager
from ..strategies import BaseStrategy, Signal
from ..utils.indicators import simple_return
from ..data import HistoricalDataService
from ..execution import OrderManager, OrderRequest


@dataclass
class BacktestResult:
    equity_curve: List[float] = field(default_factory=list)
    executed_signals: List[Signal] = field(default_factory=list)

    @property
    def total_return(self) -> float:
        if len(self.equity_curve) < 2:
            return 0.0
        start = self.equity_curve[0]
        end = self.equity_curve[-1]
        return simple_return(start, end)


class BacktestEngine:
    def __init__(
        self,
        data_service: HistoricalDataService,
        strategy: BaseStrategy,
        portfolio: PortfolioManager,
        risk_manager: RiskManager,
        order_manager: OrderManager | None = None,
    ) -> None:
        self._data_service = data_service
        self._strategy = strategy
        self._portfolio = portfolio
        self._risk = risk_manager
        self._orders = order_manager or OrderManager()

    async def run(self, symbol: str, interval: str, limit: int = 500) -> BacktestResult:
        candles = await self._data_service.fetch_candles(symbol, interval, limit)
        await self._strategy.on_start()
        marks: dict[str, float] = {}
        equity_curve: List[float] = []
        executed: List[Signal] = []
        starting_equity = self._portfolio.mark_to_market(marks)
        self._risk.reset_day(starting_equity)

        for candle in candles:
            payload = {
                'symbol': symbol,
                'price': candle['close'],
                'timestamp': candle['open_time'],
            }
            marks[symbol] = payload['price']
            signals = await self._strategy.generate_signals(payload)
            equity = self._portfolio.mark_to_market(marks)
            for signal in signals:
                allowed, _ = self._risk.validate_signal(signal, marks, equity)
                if not allowed:
                    continue
                await self._execute_signal(signal, payload['price'])
                executed.append(signal)
            equity_curve.append(self._portfolio.mark_to_market(marks))
        await self._strategy.on_stop()
        return BacktestResult(equity_curve=equity_curve, executed_signals=executed)

    async def _execute_signal(self, signal: Signal, mark_price: float) -> None:
        request = OrderRequest(
            symbol=signal.symbol,
            side=signal.side,
            quantity=signal.quantity,
            price=mark_price,
        )
        result = await self._orders.submit(request)
        notional = result.filled_quantity * (result.filled_price or mark_price)
        if signal.side == 'BUY':
            self._portfolio.update_cash(-notional)
            self._portfolio.update_position(signal.symbol, result.filled_quantity, mark_price)
        else:
            self._portfolio.update_cash(notional)
            self._portfolio.update_position(signal.symbol, -result.filled_quantity, mark_price)


__all__ = ['BacktestEngine', 'BacktestResult']
