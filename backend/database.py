"""Database utilities for the Meals Planner Codex application."""

from __future__ import annotations

import os
from typing import Final

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

_DATABASE_URL_ENV: Final = "DATABASE_URL"


def _resolve_database_url() -> str:
    """Return the configured database URL."""

    env_value = os.getenv(_DATABASE_URL_ENV)
    if env_value and env_value.strip():
        return env_value
    raise RuntimeError(
        "The DATABASE_URL environment variable is required. Set it to a "
        "PostgreSQL connection string (e.g. postgresql+psycopg2://user:pass@host/db)."
    )


DATABASE_URL = _resolve_database_url()

_POOL_SIZE = int(os.getenv("SQLALCHEMY_POOL_SIZE", "5"))
_MAX_OVERFLOW = int(os.getenv("SQLALCHEMY_MAX_OVERFLOW", "10"))

engine_kwargs: dict[str, object] = {
    "future": True,
    "pool_pre_ping": True,
    "pool_size": _POOL_SIZE,
    "max_overflow": _MAX_OVERFLOW,
    "isolation_level": "READ COMMITTED",
}

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
        "init_db() is no longer supported. The application manages schema creation "
        "automatically during startup."
    )
