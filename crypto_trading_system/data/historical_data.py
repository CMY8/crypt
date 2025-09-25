"""Historical data loading helpers backed by the persistence layer."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional

from ..config import Settings
from ..database import DatabaseManager
from ..database.models import CandleRecord


logger = logging.getLogger(__name__)


class HistoricalDataService:
    """Provides access to candle history via the configured database."""

    def __init__(
        self,
        settings: Settings,
        database: Optional[DatabaseManager] = None,
    ) -> None:
        self._settings = settings
        self._database = database
        if self._database is None:
            try:
                self._database = DatabaseManager(settings.database_url)
            except Exception as error:  # pragma: no cover - defensive
                logger.warning('Historical data service running without database: %s', error)
                self._database = None

    async def fetch_candles(
        self,
        symbol: str,
        interval: str,
        limit: int = 500,
    ) -> List[Dict[str, float]]:
        """Return candles from the database, falling back to synthetic data."""

        records: List[CandleRecord] = []
        if self._database is not None:
            records = await asyncio.to_thread(
                self._database.load_candles,
                symbol,
                interval,
                limit,
            )
        if records:
            return [self._serialize_record(record) for record in records]
        logger.debug('No cached candles for %s %s; generating synthetic series', symbol, interval)
        synthetic = await self._generate_synthetic(symbol, interval, limit)
        return synthetic

    async def store_candles(
        self,
        candles: Iterable[CandleRecord | Dict[str, Any]],
        *,
        symbol: Optional[str] = None,
        interval: Optional[str] = None,
    ) -> None:
        """Persist candles to the backing database if configured."""

        if self._database is None:
            logger.debug('Skipping candle persistence because no database is configured')
            return
        records = [
            candle
            if isinstance(candle, CandleRecord)
            else self._record_from_dict(candle, symbol=symbol, interval=interval)
            for candle in candles
        ]
        if not records:
            return
        await asyncio.to_thread(self._database.store_candles, records)

    async def _generate_synthetic(self, symbol: str, interval: str, limit: int) -> List[Dict[str, float]]:
        await asyncio.sleep(0)
        now = datetime.now(tz=timezone.utc)
        candles: List[Dict[str, float]] = []
        delta = self._interval_to_timedelta(interval)
        price = 100.0
        for index in range(limit):
            end = now - delta * index
            open_price = price
            close_price = price * 1.01
            high = max(open_price, close_price) * 1.01
            low = min(open_price, close_price) * 0.99
            candles.append(
                {
                    'open_time': end.timestamp(),
                    'open': round(open_price, 2),
                    'high': round(high, 2),
                    'low': round(low, 2),
                    'close': round(close_price, 2),
                    'volume': 1_000,
                }
            )
            price = close_price
        candles.reverse()
        return candles

    def _record_from_dict(
        self,
        candle: Dict[str, Any],
        *,
        symbol: Optional[str],
        interval: Optional[str],
    ) -> CandleRecord:
        resolved_symbol = candle.get('symbol', symbol)
        resolved_interval = candle.get('interval', interval)
        if resolved_symbol is None or resolved_interval is None:
            raise ValueError('symbol and interval must be provided when storing candles')
        open_time_value = candle.get('open_time')
        if isinstance(open_time_value, datetime):
            open_time = open_time_value
        else:
            open_time = datetime.fromtimestamp(float(open_time_value), tz=timezone.utc)
        return CandleRecord(
            symbol=resolved_symbol,
            interval=resolved_interval,
            open_time=open_time,
            open=float(candle['open']),
            high=float(candle['high']),
            low=float(candle['low']),
            close=float(candle['close']),
            volume=float(candle.get('volume', 0.0)),
        )

    @staticmethod
    def _serialize_record(record: CandleRecord) -> Dict[str, float]:
        return {
            'open_time': record.open_time.timestamp(),
            'open': record.open,
            'high': record.high,
            'low': record.low,
            'close': record.close,
            'volume': record.volume,
        }

    @staticmethod
    def _interval_to_timedelta(interval: str) -> timedelta:
        mapping = {
            '1m': timedelta(minutes=1),
            '5m': timedelta(minutes=5),
            '15m': timedelta(minutes=15),
            '1h': timedelta(hours=1),
            '1d': timedelta(days=1),
        }
        if interval not in mapping:
            raise ValueError(f'Unsupported interval: {interval}')
        return mapping[interval]


__all__ = ['HistoricalDataService']
