"""Integration-style tests for :mod:`crypto_trading_system.execution.execution_engine`."""

from __future__ import annotations

import asyncio

import pytest

from crypto_trading_system.config import Settings
from crypto_trading_system.execution import ExecutionEngine, OrderRequest, OrderResult
from crypto_trading_system.risk import PortfolioManager, RiskLimits, RiskManager
from crypto_trading_system.strategies import BaseStrategy, Signal


class StubDataManager:
    def __init__(self) -> None:
        self.subscriptions: dict[str, list] = {}
        self.started: bool = False
        self.stopped: bool = False
        self.last_symbols: list[str] | None = None

    def subscribe(self, symbol: str, listener) -> None:
        self.subscriptions.setdefault(symbol, []).append(listener)

    async def start_live_stream(self, symbols) -> None:
        self.started = True
        self.last_symbols = list(symbols)

    async def stop_live_stream(self) -> None:
        self.stopped = True


class StubOrderManager:
    def __init__(self) -> None:
        self.submitted: list[OrderRequest] = []
        self.fill_price: float | None = None
        self.close_called: bool = False

    async def submit(self, request: OrderRequest) -> OrderResult:
        self.submitted.append(request)
        price = self.fill_price if self.fill_price is not None else request.price
        return OrderResult(
            order_id='1',
            status='FILLED',
            filled_quantity=request.quantity,
            filled_price=price,
            raw={'stub': True},
        )

    async def close(self) -> None:
        self.close_called = True


class StubStrategy(BaseStrategy):
    def __init__(self, settings: Settings, signals: list[Signal]) -> None:
        super().__init__('stub', settings)
        self._signals = signals
        self.payloads: list[dict] = []

    async def generate_signals(self, payload):
        self.payloads.append(payload)
        return list(self._signals)

async def _exercise_engine() -> None:
    settings = Settings()
    data_manager = StubDataManager()
    portfolio = PortfolioManager(starting_cash=1_000.0)
    risk_limits = RiskLimits(max_position_pct=1.0, max_daily_loss_pct=1.0, max_positions=5)
    risk_manager = RiskManager(portfolio, limits=risk_limits)
    order_manager = StubOrderManager()
    order_manager.fill_price = 101.5
    engine = ExecutionEngine(data_manager, portfolio, risk_manager, order_manager)
    strategy = StubStrategy(settings, [Signal(symbol='BTCUSDT', side='BUY', quantity=1.0)])
    engine.register_strategy(strategy)

    assert engine.strategies == (strategy,)

    await engine.start(['BTCUSDT'])
    assert data_manager.started is True
    assert data_manager.last_symbols == ['BTCUSDT']

    listener = data_manager.subscriptions['BTCUSDT'][0]
    await listener({'symbol': 'BTCUSDT', 'price': 100.0})

    assert order_manager.submitted
    request = order_manager.submitted[0]
    assert isinstance(request, OrderRequest)
    assert request.symbol == 'BTCUSDT'
    assert portfolio.cash == pytest.approx(1_000.0 - 101.5)
    position = portfolio.positions['BTCUSDT']
    assert position.quantity == pytest.approx(1.0)
    assert position.average_price == pytest.approx(101.5)
    assert strategy.payloads == [{'symbol': 'BTCUSDT', 'price': 100.0}]

    await engine.stop()
    assert data_manager.stopped is True
    assert order_manager.close_called is True


def test_execution_engine_processes_signal_and_updates_portfolio() -> None:
    asyncio.run(_exercise_engine())
