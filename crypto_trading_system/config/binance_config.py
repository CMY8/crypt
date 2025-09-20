"""Binance exchange specific settings."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal, Mapping

from .config import Settings

Network = Literal['mainnet', 'testnet']
StreamType = Literal['mini_ticker', 'ticker']


@dataclass
class BinanceConfig:
    """Normalized representation of Binance API configuration."""

    api_key: str
    api_secret: str
    network: Network = 'testnet'
    recv_window: int = 5_000
    request_timeout: int = 10
    stream_type: StreamType = 'mini_ticker'
    base_url: str | None = None

    def __post_init__(self) -> None:
        if self.network not in {'mainnet', 'testnet'}:
            raise ValueError(f'Unsupported network: {self.network}')
        if self.stream_type not in {'mini_ticker', 'ticker'}:
            raise ValueError(f'Unsupported stream type: {self.stream_type}')
        if not self.base_url:
            self.base_url = self._default_base_url(self.network)

    @staticmethod
    def _default_base_url(network: Network) -> str:
        return 'https://testnet.binance.vision' if network == 'testnet' else 'https://api.binance.com'

    @property
    def ws_url(self) -> str:
        return 'wss://stream.binance.com:9443' if self.network == 'mainnet' else 'wss://testnet.binance.vision'

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key and self.api_secret)

    @classmethod
    def from_env(
        cls,
        settings: Settings,
        environ: Mapping[str, str] | None = None,
    ) -> 'BinanceConfig':
        env = environ or os.environ
        network: Network = 'testnet' if settings.use_testnet else 'mainnet'
        return cls(
            api_key=env.get('BINANCE_API_KEY', ''),
            api_secret=env.get('BINANCE_API_SECRET', ''),
            network=network,
            recv_window=int(env.get('BINANCE_RECV_WINDOW', cls.recv_window)),
            request_timeout=int(env.get('BINANCE_API_TIMEOUT', cls.request_timeout)),
            stream_type=env.get('BINANCE_STREAM_TYPE', cls.stream_type),
        )


__all__ = ['BinanceConfig', 'Network', 'StreamType']
