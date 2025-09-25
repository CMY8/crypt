"""SQLAlchemy ORM models and typed records for persistence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import DateTime, Float, Index, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all ORM models."""


class Candle(Base):
    """Represents an OHLCV candle for a given symbol and interval."""

    __tablename__ = 'candles'
    __table_args__ = (
        Index('ix_candles_symbol_interval', 'symbol', 'interval'),
    )

    symbol: Mapped[str] = mapped_column(String(32), primary_key=True)
    interval: Mapped[str] = mapped_column(String(12), primary_key=True)
    open_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    open: Mapped[float] = mapped_column(Float)
    high: Mapped[float] = mapped_column(Float)
    low: Mapped[float] = mapped_column(Float)
    close: Mapped[float] = mapped_column(Float)
    volume: Mapped[float] = mapped_column(Float)


class Trade(Base):
    """Represents an executed trade."""

    __tablename__ = 'trades'

    trade_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    side: Mapped[str] = mapped_column(String(12))
    quantity: Mapped[float] = mapped_column(Float)
    price: Mapped[float] = mapped_column(Float)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class Order(Base):
    """Represents an order submitted to the exchange."""

    __tablename__ = 'orders'

    order_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    side: Mapped[str] = mapped_column(String(12))
    status: Mapped[str] = mapped_column(String(24))
    quantity: Mapped[float] = mapped_column(Float)
    price: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


@dataclass(slots=True)
class CandleRecord:
    """Typed container used when inserting or retrieving candle data."""

    symbol: str
    interval: str
    open_time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(slots=True)
class TradeRecord:
    """Typed container for trade persistence."""

    trade_id: str
    symbol: str
    side: str
    quantity: float
    price: float
    timestamp: datetime


@dataclass(slots=True)
class OrderRecord:
    """Typed container for order persistence."""

    order_id: str
    symbol: str
    side: str
    status: str
    quantity: float
    price: float | None
    created_at: datetime


__all__ = [
    'Base',
    'Candle',
    'Trade',
    'Order',
    'CandleRecord',
    'TradeRecord',
    'OrderRecord',
]
