"""Shared Binance client management."""

from __future__ import annotations

import asyncio
from typing import Optional

from ..config import BinanceConfig

try:  # pragma: no cover - optional dependency check
    from binance import AsyncClient
    from binance.streams import BinanceSocketManager
    from binance.exceptions import BinanceAPIException, BinanceRequestException
except ImportError:  # pragma: no cover - handled at runtime
    AsyncClient = None  # type: ignore
    BinanceSocketManager = None  # type: ignore
    BinanceAPIException = BinanceRequestException = Exception  # type: ignore


class BinanceService:
    """Lazily instantiates Binance AsyncClient and socket manager."""

    def __init__(self, config: BinanceConfig) -> None:
        if AsyncClient is None:
            raise RuntimeError(
                'python-binance is not installed. Install dependencies from '
                'crypto_trading_system/requirements.txt to enable live trading.'
            )
        self._config = config
        self._client: Optional[AsyncClient] = None
        self._socket_manager: Optional[BinanceSocketManager] = None
        self._lock = asyncio.Lock()

    @property
    def config(self) -> BinanceConfig:
        return self._config

    async def client(self) -> AsyncClient:
        async with self._lock:
            if self._client is None:
                self._client = await AsyncClient.create(
                    api_key=self._config.api_key,
                    api_secret=self._config.api_secret,
                    testnet=self._config.network == 'testnet',
                    requests_params={'timeout': self._config.request_timeout},
                )
                self._client.API_URL = self._config.base_url  # type: ignore[attr-defined]
            return self._client

    async def socket_manager(self) -> BinanceSocketManager:
        async with self._lock:
            if self._socket_manager is None:
                client = await self.client()
                self._socket_manager = BinanceSocketManager(client)
            return self._socket_manager

    async def close(self) -> None:
        async with self._lock:
            if self._socket_manager is not None:
                await self._socket_manager.close()
                self._socket_manager = None
            if self._client is not None:
                await self._client.close_connection()
                self._client = None


__all__ = ['BinanceService', 'BinanceAPIException', 'BinanceRequestException']
