"""Assorted helper functions."""

from __future__ import annotations

import asyncio
import functools
from typing import Any, Awaitable, Callable, Iterable, List, Sequence, Tuple, Type


def async_retry(
    retries: int = 3,
    delay: float = 0.5,
    exceptions: Tuple[Type[BaseException], ...] = (Exception,),
) -> Callable[[Callable[..., Awaitable[Any]]], Callable[..., Awaitable[Any]]]:
    """Retry decorator for async callables."""

    def decorator(func: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            attempt = 0
            while True:
                try:
                    return await func(*args, **kwargs)
                except exceptions:
                    attempt += 1
                    if attempt >= retries:
                        raise
                    await asyncio.sleep(delay * attempt)
        return wrapper

    return decorator


def chunked(sequence: Sequence[Any], size: int) -> Iterable[List[Any]]:
    """Yield chunks from the sequence."""
    chunk: List[Any] = []
    for item in sequence:
        chunk.append(item)
        if len(chunk) == size:
            yield chunk
            chunk = []
    if chunk:
        yield chunk


__all__ = ['async_retry', 'chunked']
