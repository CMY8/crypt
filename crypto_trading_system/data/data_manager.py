"""Coordinates real-time and historical data pipelines."""

from __future__ import annotations

import asyncio
import contextlib
from collections import defaultdict
from typing import Awaitable, Callable, Dict, Iterable, List, Optional

from ..config import Settings
from .historical_data import HistoricalDataService
from .websocket_client import WebSocketClient

Listener = Callable[[Dict[str, float]], Awaitable[None]]


class DataManager:
    """High level data orchestrator."""

    def __init__(
        self,
        settings: Settings,
        websocket_client: Optional[WebSocketClient] = None,
        historical_service: Optional[HistoricalDataService] = None,
    ) -> None:
        self._settings = settings
        self._ws_client = websocket_client or WebSocketClient(settings)
        self._historical = historical_service or HistoricalDataService(settings)
        self._listeners: Dict[str, List[Listener]] = defaultdict(list)
        self._stream_task: Optional[asyncio.Task[None]] = None

    async def start_live_stream(self, symbols: Iterable[str]) -> None:
        if self._stream_task and not self._stream_task.done():
            raise RuntimeError('Live stream already running')

        async def _runner() -> None:
            async for update in self._ws_client.stream(symbols):
                await self._publish(update)

        self._stream_task = asyncio.create_task(_runner())

    async def stop_live_stream(self) -> None:
        await self._ws_client.disconnect()
        if self._stream_task:
            self._stream_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._stream_task
            self._stream_task = None

    def subscribe(self, symbol: str, listener: Listener) -> None:
        if listener not in self._listeners[symbol]:
            self._listeners[symbol].append(listener)

    def unsubscribe(self, symbol: str, listener: Listener) -> None:
        listeners = self._listeners.get(symbol)
        if not listeners:
            return
        with contextlib.suppress(ValueError):
            listeners.remove(listener)
        if not listeners:
            self._listeners.pop(symbol, None)

    async def historical_candles(
        self,
        symbol: str,
        interval: str,
        limit: int = 500,
    ) -> List[Dict[str, float]]:
        return await self._historical.fetch_candles(symbol, interval, limit)

    async def _publish(self, update: Dict[str, float]) -> None:
        symbol = update.get('symbol')
        if not symbol:
            return
        for listener in list(self._listeners.get(symbol, [])):
            await listener(update)


__all__ = ['DataManager']
