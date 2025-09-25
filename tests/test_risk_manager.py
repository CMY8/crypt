"""Unit tests for :mod:`crypto_trading_system.risk.risk_manager`."""

from crypto_trading_system.risk import PortfolioManager, Position, RiskLimits, RiskManager
from crypto_trading_system.strategies import Signal


def test_validate_signal_rejects_missing_mark() -> None:
    portfolio = PortfolioManager(starting_cash=1_000.0)
    risk_manager = RiskManager(portfolio)
    signal = Signal(symbol='BTCUSDT', side='BUY', quantity=1.0)

    allowed, reason = risk_manager.validate_signal(signal, marks={}, equity=1_000.0)

    assert not allowed
    assert reason == 'Missing mark price'


def test_validate_signal_enforces_position_limit() -> None:
    portfolio = PortfolioManager(starting_cash=10_000.0)
    risk_manager = RiskManager(portfolio)
    signal = Signal(symbol='BTCUSDT', side='BUY', quantity=1.0)

    allowed, reason = risk_manager.validate_signal(
        signal,
        marks={'BTCUSDT': 2_000.0},
        equity=10_000.0,
    )

    assert not allowed
    assert reason == 'Position size exceeds risk limit'


def test_validate_signal_enforces_max_positions() -> None:
    portfolio = PortfolioManager(starting_cash=5_000.0)
    risk_limits = RiskLimits(max_positions=2)
    risk_manager = RiskManager(portfolio, limits=risk_limits)
    portfolio.positions['ETHUSDT'] = Position(symbol='ETHUSDT', quantity=1.0, average_price=1_000.0)
    portfolio.positions['BNBUSDT'] = Position(symbol='BNBUSDT', quantity=1.0, average_price=300.0)
    signal = Signal(symbol='BTCUSDT', side='BUY', quantity=0.01)

    allowed, reason = risk_manager.validate_signal(
        signal,
        marks={'BTCUSDT': 20_000.0},
        equity=5_000.0,
    )

    assert not allowed
    assert reason == 'Maximum concurrent positions reached'


def test_validate_signal_enforces_drawdown_limit() -> None:
    portfolio = PortfolioManager(starting_cash=10_000.0)
    risk_limits = RiskLimits(max_daily_loss_pct=0.05)
    risk_manager = RiskManager(portfolio, limits=risk_limits)
    risk_manager.reset_day(starting_equity=10_000.0)
    signal = Signal(symbol='BTCUSDT', side='BUY', quantity=0.01)

    allowed, reason = risk_manager.validate_signal(
        signal,
        marks={'BTCUSDT': 10_000.0},
        equity=9_000.0,
    )

    assert not allowed
    assert reason == 'Daily loss limit breached'
