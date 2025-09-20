"""Coordinates strategies, risk checks, and order routing."""

from __future__ import annotations

import asyncio
import logging
from typing import Iterable, List, Optional

from ..data import DataManager
from ..monitoring import DashboardState
from ..risk import PortfolioManager, RiskManager
from ..strategies import BaseStrategy, Signal
from .order_manager import OrderManager, OrderRequest

logger = logging.getLogger(__name__)


class ExecutionEngine:
    """Runs the trading loop by wiring strategies to execution."""

    def __init__(
        self,
        data_manager: DataManager,
        portfolio: PortfolioManager,
        risk_manager: RiskManager,
        order_manager: OrderManager,
        dashboard: Optional[DashboardState] = None,
    ) -> None:
        self._data_manager = data_manager
        self._portfolio = portfolio
        self._risk = risk_manager
        self._orders = order_manager
        self._dashboard = dashboard
        self._strategies: List[BaseStrategy] = []
        self._marks: dict[str, float] = {}
        self._symbols: List[str] = []

    def register_strategy(self, strategy: BaseStrategy) -> None:
        self._strategies.append(strategy)

    async def start(self, symbols: Iterable[str]) -> None:
        self._symbols = list(symbols)
        equity = self._portfolio.mark_to_market(self._marks)
        self._risk.reset_day(equity)
        for strategy in self._strategies:
            await strategy.on_start()
        for symbol in self._symbols:
            self._data_manager.subscribe(symbol, self._handle_tick)
        await self._data_manager.start_live_stream(self._symbols)

    async def stop(self) -> None:
        await self._data_manager.stop_live_stream()
        for strategy in self._strategies:
            await strategy.on_stop()

    async def _handle_tick(self, payload: dict) -> None:
        symbol = payload['symbol']
        price = payload['price']
        self._marks[symbol] = price
        if self._dashboard:
            self._dashboard.update_mark(symbol, price)
        equity = self._portfolio.mark_to_market(self._marks)
        tasks = [strategy.on_data(payload) for strategy in self._strategies]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        signals: List[Signal] = []
        for result, strategy in zip(results, self._strategies):
            if isinstance(result, Exception):
                await strategy.on_error(result)
                continue
            signals.extend(result)
        for signal in signals:
            allowed, reason = self._risk.validate_signal(signal, self._marks, equity)
            if not allowed:
                logger.debug('Signal rejected: %s (%s)', signal, reason)
                continue
            await self._execute_signal(signal, price)

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
        logger.info('Executed %s -> %s', signal, result)


__all__ = ['ExecutionEngine']
