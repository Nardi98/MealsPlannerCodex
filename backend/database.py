"""Database utilities for the Meals Planner Codex application."""

from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# Absolute path to the local SQLite fallback file, under the backend's ``data``
# directory. Built from the module location so tests and the app behave the same
# regardless of the current working directory.
_BASE_DIR = Path(__file__).resolve().parent
_SQLITE_FALLBACK_URL = f"sqlite:///{_BASE_DIR / 'data' / 'app.db'}"


def resolve_database_url() -> tuple[str, dict]:
    """Resolve the SQLAlchemy URL and engine ``connect_args`` from the env.

    Honors the ``DATABASE_URL`` environment variable (which Railway injects),
    falling back to a local SQLite file when it is unset. Railway sometimes
    emits the bare ``postgres://`` scheme, which SQLAlchemy rejects, so it is
    normalized to ``postgresql://``. SQLite-only ``connect_args`` are applied
    only when the resolved URL is SQLite.
    """

    url = os.environ.get("DATABASE_URL") or _SQLITE_FALLBACK_URL
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]

    if url.startswith("sqlite"):
        return url, {"check_same_thread": False}
    return url, {}


# SQLAlchemy database URL for the application.
DATABASE_URL, _CONNECT_ARGS = resolve_database_url()

# Create the core SQLAlchemy engine and session factory. ``future=True`` enables
# 2.0 style usage which is what this project is targeting.
engine = create_engine(DATABASE_URL, future=True, connect_args=_CONNECT_ARGS)

SessionLocal = sessionmaker(
    bind=engine, autoflush=False, autocommit=False, future=True
)

# Base class for declarative models. All ORM models in the project should
# inherit from this ``Base`` so that ``Base.metadata`` contains all tables.
Base = declarative_base()


def init_db() -> None:
    """Create database tables.

    Applications can call this on startup to ensure all tables are created in
    the configured database. It is safe to call multiple times; existing tables
    are left untouched.
    """

    Base.metadata.create_all(bind=engine)
