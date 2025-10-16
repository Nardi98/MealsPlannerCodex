"""Database utilities for the Meals Planner Codex application."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Final

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

_DATABASE_URL_ENV: Final = "DATABASE_URL"
_BASE_DIR = Path(__file__).resolve().parent
_SQLITE_FALLBACK = f"sqlite:///{_BASE_DIR / 'data' / 'app.db'}"


def _resolve_database_url() -> tuple[str, bool]:
    """Return the configured database URL and whether it is a fallback."""

    env_value = os.getenv(_DATABASE_URL_ENV)
    if env_value and env_value.strip():
        return env_value, False
    return _SQLITE_FALLBACK, True


DATABASE_URL, USING_DEV_FALLBACK = _resolve_database_url()

if not DATABASE_URL:
    raise RuntimeError(
        "The DATABASE_URL environment variable is required. Set it to a "
        "PostgreSQL connection string (e.g. postgresql+psycopg2://user:pass@host/db)."
    )

_POOL_SIZE = int(os.getenv("SQLALCHEMY_POOL_SIZE", "5"))
_MAX_OVERFLOW = int(os.getenv("SQLALCHEMY_MAX_OVERFLOW", "10"))

engine_kwargs: dict[str, object] = {
    "future": True,
    "pool_pre_ping": True,
}

if DATABASE_URL.startswith("postgresql"):
    engine_kwargs.update(
        pool_size=_POOL_SIZE,
        max_overflow=_MAX_OVERFLOW,
        isolation_level="READ COMMITTED",
    )
else:
    # Ensure the SQLite developer fallback remains usable.
    engine_kwargs.setdefault("connect_args", {"check_same_thread": False})

engine = create_engine(DATABASE_URL, **engine_kwargs)

SessionLocal = sessionmaker(
    bind=engine, autoflush=False, autocommit=False, future=True
)

# Base class for declarative models. All ORM models in the project should
# inherit from this ``Base`` so that ``Base.metadata`` contains all tables.
Base = declarative_base()


def init_db() -> None:
    """Deprecated helper retained for backwards compatibility."""

    raise RuntimeError(
        "init_db() is no longer supported. Run Alembic migrations instead with "
        "'alembic upgrade head'."
    )
