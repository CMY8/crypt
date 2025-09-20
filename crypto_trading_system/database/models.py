"""Lightweight data models for persistence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class Candle:
    symbol: str
    open_time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass
class TradeRecord:
    trade_id: str
    symbol: str
    side: str
    quantity: float
    price: float
    timestamp: datetime


@dataclass
class OrderRecord:
    order_id: str
    symbol: str
    side: str
    status: str
    quantity: float
    price: float | None
    created_at: datetime


__all__ = ['Candle', 'TradeRecord', 'OrderRecord']
