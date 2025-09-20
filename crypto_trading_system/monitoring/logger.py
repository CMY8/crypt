"""Logging helpers."""

from __future__ import annotations

import logging
from typing import Optional


def configure_logging(level: str = 'INFO', *, include_timestamp: bool = True) -> None:
    """Configure root logging handlers."""
    fmt = '%(asctime)s - %(name)s - %(levelname)s - %(message)s' if include_timestamp else '%(name)s - %(levelname)s - %(message)s'
    logging.basicConfig(level=getattr(logging, level.upper(), logging.INFO), format=fmt)


__all__ = ['configure_logging']
