"""Defines the base strategy contract."""

from __future__ import annotations

import abc
import logging
from dataclasses import dataclass
from typing import Dict, Iterable, List, Literal, Optional

from ..config import Settings

Side = Literal['BUY', 'SELL']

logger = logging.getLogger(__name__)


@dataclass
class Signal:
    symbol: str
    side: Side
    quantity: float
    confidence: float = 1.0
    metadata: Optional[Dict[str, float]] = None


class BaseStrategy(abc.ABC):
    """Common lifecycle hooks shared by all strategies."""

    def __init__(self, name: str, settings: Settings) -> None:
        self.name = name
        self.settings = settings
        self._is_running = False

    async def on_start(self) -> None:
        logger.info('Starting strategy %s', self.name)
        self._is_running = True

    async def on_stop(self) -> None:
        logger.info('Stopping strategy %s', self.name)
        self._is_running = False

    async def on_data(self, payload: Dict[str, float]) -> Iterable[Signal]:
        if not self._is_running:
            return []
        return await self.generate_signals(payload)

    @abc.abstractmethod
    async def generate_signals(self, payload: Dict[str, float]) -> Iterable[Signal]:
        """Return zero or more trade signals for the latest data payload."""

    def filter_positions(self, positions: Dict[str, float]) -> Dict[str, float]:
        return positions

    async def on_error(self, error: Exception) -> None:
        logger.exception('Unhandled strategy error: %s', error)


__all__ = ['BaseStrategy', 'Signal', 'Side']
