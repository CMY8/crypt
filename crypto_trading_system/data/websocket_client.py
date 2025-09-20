"""Binance websocket client with mock fallback."""

from __future__ import annotations

import asyncio
import random
import time
from typing import AsyncIterator, Iterable, Optional

from ..config import Settings, BinanceConfig
from ..exchanges import BinanceService


class WebSocketClient:
    """Yield live ticks from Binance or synthetic data when unavailable."""

    def __init__(
        self,
        settings: Settings,
        config: Optional[BinanceConfig] = None,
        service: Optional[BinanceService] = None,
    ) -> None:
        self._settings = settings
        self._config = config or BinanceConfig.from_env(settings)
        self._service: Optional[BinanceService] = None
        self._rng = random.Random(time.time())
        if service is not None:
            self._service = service
        elif self._config.is_configured:
            try:
                self._service = BinanceService(self._config)
            except RuntimeError:
                self._service = None

    async def connect(self) -> None:
        if self._service is not None:
            await self._service.client()

    async def disconnect(self) -> None:
        if self._service is not None:
            await self._service.close()

    async def stream(self, symbols: Iterable[str]) -> AsyncIterator[dict]:
        if self._service is None:
            async for update in self._mock_stream(symbols):
                yield update
            return

        manager = await self._service.socket_manager()
        stream_names = [self._stream_name(symbol) for symbol in symbols]
        socket = manager.multiplex_socket(stream_names)
        async with socket as stream:
            async for message in stream:
                data = message.get('data', message)
                yield {
                    'symbol': data['s'],
                    'price': float(data['c']),
                    'timestamp': int(data['E']) / 1000,
                    'volume': float(data.get('v', 0.0)),
                    'raw': data,
                }

    async def _mock_stream(self, symbols: Iterable[str]) -> AsyncIterator[dict]:
        tracked = list(symbols) or ['BTCUSDT']
        base_price = {symbol: self._rng.uniform(10_000, 60_000) for symbol in tracked}
        while True:
            await asyncio.sleep(1)
            symbol = self._rng.choice(tracked)
            change = self._rng.uniform(-0.5, 0.5)
            base_price[symbol] += change
            yield {
                'symbol': symbol,
                'price': round(base_price[symbol], 2),
                'timestamp': time.time(),
                'volume': 0.0,
                'raw': {'mock': True},
            }

    def _stream_name(self, symbol: str) -> str:
        suffix = 'miniTicker' if self._config.stream_type == 'mini_ticker' else 'ticker'
        return f"{symbol.lower()}@{suffix}"


__all__ = ['WebSocketClient']
