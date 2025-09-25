"""Pytest configuration ensuring imports work without optional deps."""

from __future__ import annotations

import sys
import types
from pathlib import Path


def _ensure_sqlalchemy_stub() -> None:
    try:
        import sqlalchemy  # type: ignore  # noqa: F401
        return
    except ModuleNotFoundError:
        pass

    def _not_available(*_args, **_kwargs):  # pragma: no cover - simple stub
        raise RuntimeError('SQLAlchemy is required for database features')

    sa_module = types.ModuleType('sqlalchemy')
    sa_module.Select = type('Select', (), {})
    sa_module.create_engine = _not_available
    sa_module.select = _not_available
    sa_module.DateTime = lambda *args, **kwargs: None
    sa_module.Float = lambda *args, **kwargs: None
    sa_module.Index = lambda *args, **kwargs: None
    sa_module.String = lambda *args, **kwargs: None

    engine_module = types.ModuleType('sqlalchemy.engine')
    engine_module.Engine = type('Engine', (), {})

    orm_module = types.ModuleType('sqlalchemy.orm')
    orm_module.DeclarativeBase = type('DeclarativeBase', (), {})
    orm_module.Mapped = object
    orm_module.mapped_column = lambda *args, **kwargs: None
    orm_module.Session = type('Session', (), {})
    orm_module.sessionmaker = _not_available

    sa_module.engine = engine_module
    sa_module.orm = orm_module

    sys.modules['sqlalchemy'] = sa_module
    sys.modules['sqlalchemy.engine'] = engine_module
    sys.modules['sqlalchemy.orm'] = orm_module


_ensure_sqlalchemy_stub()

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
