"""Performance metric utilities."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, List


def _ensure_list(values: Iterable[float]) -> List[float]:
    if isinstance(values, list):
        return values
    return list(values)


def _drawdowns(equity_curve: List[float]) -> List[float]:
    peaks: List[float] = []
    drawdowns: List[float] = []
    max_peak = float('-inf')
    for value in equity_curve:
        max_peak = max(max_peak, value)
        peaks.append(max_peak)
        drawdowns.append((max_peak - value) / max_peak if max_peak else 0.0)
    return drawdowns


@dataclass
class PerformanceMetrics:
    returns: List[float]

    def sharpe_ratio(self, risk_free: float = 0.0) -> float:
        if len(self.returns) < 2:
            return 0.0
        excess = [r - risk_free for r in self.returns]
        avg = sum(excess) / len(excess)
        variance = sum((r - avg) ** 2 for r in excess) / (len(excess) - 1)
        std_dev = math.sqrt(variance)
        if std_dev == 0:
            return 0.0
        return avg / std_dev * math.sqrt(252)

    def max_drawdown(self, equity_curve: Iterable[float]) -> float:
        curve = _ensure_list(equity_curve)
        if not curve:
            return 0.0
        return max(_drawdowns(curve))


__all__ = ['PerformanceMetrics']
