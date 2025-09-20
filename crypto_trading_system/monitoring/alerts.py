"""Alerting primitives."""

from __future__ import annotations

import asyncio
import enum
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from typing import Deque, Iterable


class AlertLevel(str, enum.Enum):
    INFO = 'INFO'
    WARNING = 'WARNING'
    CRITICAL = 'CRITICAL'


@dataclass
class Alert:
    message: str
    level: AlertLevel
    created_at: datetime = datetime.utcnow()


class AlertManager:
    """In-memory alert buffer suitable for piping into the dashboard."""

    def __init__(self, max_alerts: int = 100) -> None:
        self._alerts: Deque[Alert] = deque(maxlen=max_alerts)
        self._queue: asyncio.Queue[Alert] = asyncio.Queue()

    def emit(self, alert: Alert) -> None:
        self._alerts.append(alert)
        self._queue.put_nowait(alert)

    async def next(self) -> Alert:
        return await self._queue.get()

    def latest(self, limit: int = 10) -> Iterable[Alert]:
        return list(self._alerts)[-limit:]


__all__ = ['Alert', 'AlertLevel', 'AlertManager']
