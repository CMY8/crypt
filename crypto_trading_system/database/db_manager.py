"""SQLAlchemy-backed persistence manager."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Iterator, List

from sqlalchemy import Select, create_engine, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from .models import (
    Base,
    Candle,
    CandleRecord,
    Order,
    OrderRecord,
    Trade,
    TradeRecord,
)


def _as_utc(value: datetime) -> datetime:
    """Ensure datetimes are timezone-aware in UTC."""

    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


class DatabaseManager:
    """High level helper around a SQLAlchemy engine and session factory."""

    def __init__(self, database_url: str, *, echo: bool = False) -> None:
        self._database_url = database_url
        connect_args: dict[str, object] = {}
        if database_url.startswith('sqlite:///'):
            db_path = Path(database_url.replace('sqlite:///', '', 1))
            db_path.parent.mkdir(parents=True, exist_ok=True)
            connect_args['check_same_thread'] = False
        self._engine: Engine = create_engine(
            database_url,
            echo=echo,
            future=True,
            connect_args=connect_args,
        )
        self._session_factory = sessionmaker(
            self._engine,
            expire_on_commit=False,
            future=True,
        )
        self.create_schema()

    def create_schema(self) -> None:
        """Create database tables if they do not already exist."""

        Base.metadata.create_all(self._engine)

    @contextmanager
    def session(self) -> Iterator[Session]:
        """Context manager returning a database session with automatic commit."""

        session: Session = self._session_factory()
        try:
            yield session
            session.commit()
        except Exception:  # pragma: no cover - re-raise after rollback
            session.rollback()
            raise
        finally:
            session.close()

    def store_candles(self, candles: Iterable[CandleRecord]) -> None:
        """Insert or update OHLCV candles."""

        candle_list = list(candles)
        if not candle_list:
            return
        with self.session() as session:
            for candle in candle_list:
                session.merge(
                    Candle(
                        symbol=candle.symbol,
                        interval=candle.interval,
                        open_time=_as_utc(candle.open_time),
                        open=candle.open,
                        high=candle.high,
                        low=candle.low,
                        close=candle.close,
                        volume=candle.volume,
                    )
                )

    def load_candles(self, symbol: str, interval: str, limit: int) -> List[CandleRecord]:
        """Return the most recent candles ordered from oldest to newest."""

        if limit <= 0:
            return []
        stmt: Select[tuple[Candle]] = (
            select(Candle)
            .where(Candle.symbol == symbol, Candle.interval == interval)
            .order_by(Candle.open_time.desc())
            .limit(limit)
        )
        with self.session() as session:
            rows = session.execute(stmt).scalars().all()
        return [
            CandleRecord(
                symbol=row.symbol,
                interval=row.interval,
                open_time=_as_utc(row.open_time),
                open=row.open,
                high=row.high,
                low=row.low,
                close=row.close,
                volume=row.volume,
            )
            for row in reversed(rows)
        ]

    def record_trade(self, trade: TradeRecord) -> None:
        """Persist details about an executed trade."""

        with self.session() as session:
            session.merge(
                Trade(
                    trade_id=trade.trade_id,
                    symbol=trade.symbol,
                    side=trade.side,
                    quantity=trade.quantity,
                    price=trade.price,
                    timestamp=_as_utc(trade.timestamp),
                )
            )

    def record_order(self, order: OrderRecord) -> None:
        """Persist details about a submitted order."""

        with self.session() as session:
            session.merge(
                Order(
                    order_id=order.order_id,
                    symbol=order.symbol,
                    side=order.side,
                    status=order.status,
                    quantity=order.quantity,
                    price=order.price,
                    created_at=_as_utc(order.created_at),
                )
            )

    def close(self) -> None:
        """Dispose of the underlying engine and connection pool."""

        self._engine.dispose()


__all__ = ['DatabaseManager']
