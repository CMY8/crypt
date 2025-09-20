"""Core package for the crypto trading system."""

from importlib import metadata

try:
    __version__ = metadata.version('crypto_trading_system')
except metadata.PackageNotFoundError:  # pragma: no cover
    __version__ = '0.1.0-dev'

__all__ = ['__version__']
