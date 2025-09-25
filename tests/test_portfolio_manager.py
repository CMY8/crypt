"""Tests for :mod:`crypto_trading_system.risk.portfolio_manager`."""

import pytest

from crypto_trading_system.risk import PortfolioManager


def test_update_position_accumulates_average_price() -> None:
    portfolio = PortfolioManager(starting_cash=1_000.0)

    position = portfolio.update_position('BTCUSDT', fill_quantity=1.0, fill_price=100.0)
    assert position.quantity == pytest.approx(1.0)
    assert position.average_price == pytest.approx(100.0)

    position = portfolio.update_position('BTCUSDT', fill_quantity=1.0, fill_price=110.0)
    assert position.quantity == pytest.approx(2.0)
    assert position.average_price == pytest.approx(105.0)


def test_update_position_closing_trade_resets_position() -> None:
    portfolio = PortfolioManager(starting_cash=1_000.0)
    portfolio.update_position('BTCUSDT', fill_quantity=1.0, fill_price=100.0)

    position = portfolio.update_position('BTCUSDT', fill_quantity=-1.0, fill_price=100.0)

    assert position.quantity == pytest.approx(0.0)
    assert position.average_price == pytest.approx(0.0)


def test_partial_close_long_keeps_average_price() -> None:
    portfolio = PortfolioManager(starting_cash=1_000.0)
    portfolio.update_position('BTCUSDT', fill_quantity=2.0, fill_price=100.0)

    position = portfolio.update_position('BTCUSDT', fill_quantity=-1.0, fill_price=110.0)

    assert position.quantity == pytest.approx(1.0)
    assert position.average_price == pytest.approx(100.0)


def test_partial_close_short_keeps_average_price() -> None:
    portfolio = PortfolioManager(starting_cash=1_000.0)
    portfolio.update_position('ETHUSDT', fill_quantity=-2.0, fill_price=150.0)

    position = portfolio.update_position('ETHUSDT', fill_quantity=1.0, fill_price=140.0)

    assert position.quantity == pytest.approx(-1.0)
    assert position.average_price == pytest.approx(150.0)


def test_position_flip_uses_new_fill_price() -> None:
    portfolio = PortfolioManager(starting_cash=1_000.0)
    portfolio.update_position('BTCUSDT', fill_quantity=1.0, fill_price=100.0)

    position = portfolio.update_position('BTCUSDT', fill_quantity=-2.0, fill_price=120.0)

    assert position.quantity == pytest.approx(-1.0)
    assert position.average_price == pytest.approx(120.0)


def test_mark_to_market_uses_latest_marks() -> None:
    portfolio = PortfolioManager(starting_cash=1_000.0)
    portfolio.update_position('BTCUSDT', fill_quantity=1.0, fill_price=100.0)

    equity = portfolio.mark_to_market({'BTCUSDT': 120.0})

    assert equity == pytest.approx(1_120.0)


def test_mark_to_market_falls_back_to_average_price() -> None:
    portfolio = PortfolioManager(starting_cash=500.0)
    portfolio.update_position('ETHUSDT', fill_quantity=2.0, fill_price=50.0)

    equity = portfolio.mark_to_market({})

    # Without an explicit mark the average fill price should be used.
    assert equity == pytest.approx(600.0)
