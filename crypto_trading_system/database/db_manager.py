"""Simple SQLite-backed persistence manager."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from .models import Candle, OrderRecord, TradeRecord


_SCHEMA = """
CREATE TABLE IF NOT EXISTS trades (
    trade_id TEXT PRIMARY KEY,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    quantity REAL NOT NULL,
    price REAL NOT NULL,
    timestamp TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS orders (
    order_id TEXT PRIMARY KEY,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    status TEXT NOT NULL,
    quantity REAL NOT NULL,
    price REAL,
    created_at TEXT NOT NULL
);
"""


class DatabaseManager:
    def __init__(self, database_url: str) -> None:
        if not database_url.startswith('sqlite:///'):
            raise ValueError('Only sqlite URLs are supported in the stub manager')
        db_path = database_url.replace('sqlite:///', '', 1)
        self._path = Path(db_path)
        self._connection = sqlite3.connect(self._path)
        self._connection.execute('PRAGMA journal_mode=WAL;')
        self.create_schema()

    def create_schema(self) -> None:
        self._connection.executescript(_SCHEMA)
        self._connection.commit()

    @contextmanager
    def cursor(self) -> Iterator[sqlite3.Cursor]:
        cur = self._connection.cursor()
        try:
            yield cur
            self._connection.commit()
        finally:
            cur.close()

    def record_trade(self, trade: TradeRecord) -> None:
        with self.cursor() as cur:
            cur.execute(
                'INSERT OR REPLACE INTO trades VALUES (?, ?, ?, ?, ?, ?)',
                (
                    trade.trade_id,
                    trade.symbol,
                    trade.side,
                    trade.quantity,
                    trade.price,
                    trade.timestamp.isoformat(),
                ),
            )

    def record_order(self, order: OrderRecord) -> None:
        with self.cursor() as cur:
            cur.execute(
                'INSERT OR REPLACE INTO orders VALUES (?, ?, ?, ?, ?, ?, ?)',
                (
                    order.order_id,
                    order.symbol,
                    order.side,
                    order.status,
                    order.quantity,
                    order.price,
                    order.created_at.isoformat(),
                ),
            )

    def close(self) -> None:
        self._connection.close()


__all__ = ['DatabaseManager']
