"""Historical data loading helpers."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List

from ..config import Settings


class HistoricalDataService:
    """Provides access to candle history.

    The current implementation returns synthetic data as a placeholder.
    Replace the logic in `fetch_candles` with real exchange integration or
    database lookups when ready.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def fetch_candles(self, symbol: str, interval: str, limit: int = 500) -> List[Dict[str, float]]:
        await asyncio.sleep(0)
        now = datetime.utcnow()
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
