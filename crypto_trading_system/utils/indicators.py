"""Indicator helpers."""

from __future__ import annotations

from typing import Iterable, List


def moving_average(values: Iterable[float], window: int) -> List[float]:
    values = list(values)
    if window <= 0:
        raise ValueError('window must be positive')
    if len(values) < window:
        return []
    result: List[float] = []
    for index in range(window - 1, len(values)):
        slice_ = values[index - window + 1 : index + 1]
        result.append(sum(slice_) / window)
    return result


def exponential_moving_average(values: Iterable[float], window: int) -> List[float]:
    values = list(values)
    if not values or window <= 0:
        return []
    multiplier = 2 / (window + 1)
    ema: List[float] = [values[0]]
    for price in values[1:]:
        ema.append((price - ema[-1]) * multiplier + ema[-1])
    return ema


def simple_return(start: float, end: float) -> float:
    if start == 0:
        return 0.0
    return (end - start) / start


__all__ = ['moving_average', 'exponential_moving_average', 'simple_return']
