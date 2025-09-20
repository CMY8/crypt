"""Application-wide configuration helpers."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable

_ENV_COMMENT_PREFIX = '#'


def _load_env_file(path: Path) -> Dict[str, str]:
    """Load simple KEY=VALUE pairs from a .env style file if it exists."""
    if not path.exists():
        return {}

    values: Dict[str, str] = {}
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith(_ENV_COMMENT_PREFIX):
            continue
        if '=' not in line:
            continue
        key, value = line.split('=', 1)
        values[key.strip()] = value.strip().strip('"').strip("\'")
    return values


def _merge_env(sources: Iterable[Dict[str, str]]) -> Dict[str, str]:
    merged: Dict[str, str] = {}
    for source in sources:
        merged.update(source)
    return merged


@dataclass
class Settings:
    """Container for application level settings.

    Values are resolved from (in order): process environment, `.env` file,
    and finally the provided defaults.
    """

    environment: str = 'development'
    database_url: str = 'sqlite:///data/crypto_trading.db'
    data_directory: Path = field(default_factory=lambda: Path('data'))
    log_level: str = 'INFO'
    use_testnet: bool = True
    risk_free_rate: float = 0.02

    @classmethod
    def from_env(cls, env_file: str | Path = '.env') -> 'Settings':
        env_path = Path(env_file)
        env_file_values = _load_env_file(env_path)
        merged = _merge_env([env_file_values, dict(os.environ)])

        kwargs = {
            'environment': merged.get('APP_ENV', cls.environment),
            'database_url': merged.get('DATABASE_URL', cls.database_url),
            'data_directory': merged.get('DATA_DIRECTORY', str(cls.data_directory)),
            'log_level': merged.get('LOG_LEVEL', cls.log_level),
            'use_testnet': merged.get('USE_TESTNET', str(cls.use_testnet)).lower() in {'1', 'true', 'yes'},
            'risk_free_rate': float(merged.get('RISK_FREE_RATE', cls.risk_free_rate)),
        }
        settings = cls(**kwargs)
        settings.ensure_directories()
        return settings

    def ensure_directories(self) -> None:
        """Create required directories if they are missing."""
        self.data_directory = Path(self.data_directory)
        self.data_directory.mkdir(parents=True, exist_ok=True)


load_settings = Settings.from_env

__all__ = ['Settings', 'load_settings']
