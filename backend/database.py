"""Database utilities for the Meals Planner Codex application."""

from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker


def resolve_database_url() -> str:
    """Resolve the PostgreSQL SQLAlchemy URL from the environment.

    Requires the ``DATABASE_URL`` environment variable, which Railway injects
    from the Postgres service. There is deliberately no fallback: a missing
    variable is a deployment error, and guessing a URL would let the app serve
    traffic against the wrong database. Railway sometimes emits the bare
    ``postgres://`` scheme, which SQLAlchemy rejects, so it is normalized.

    The driver is pinned to ``psycopg2`` explicitly. A bare ``postgresql://``
    URL picks whichever DBAPI the installed SQLAlchemy defaults to, and 2.1
    changed that default from ``psycopg2`` to ``psycopg`` (v3) -- which this
    image does not install, so a fresh build died at import with
    ``ModuleNotFoundError: No module named 'psycopg'``. Naming the driver here
    means the app, Alembic and every deployment resolve the same one no matter
    which SQLAlchemy is installed.
    """

    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "DATABASE_URL must be set to a PostgreSQL URL "
            "(e.g. postgresql://user:pass@host:5432/mealsdb)"
        )
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg2://" + url[len("postgresql://"):]
    return url


# SQLAlchemy database URL for the application.
DATABASE_URL = resolve_database_url()

# Create the core SQLAlchemy engine and session factory. ``future=True`` enables
# 2.0 style usage which is what this project is targeting.
engine = create_engine(DATABASE_URL, future=True)

SessionLocal = sessionmaker(
    bind=engine, autoflush=False, autocommit=False, future=True
)

# Base class for declarative models. All ORM models in the project should
# inherit from this ``Base`` so that ``Base.metadata`` contains all tables.
Base = declarative_base()


def get_db():
    """FastAPI dependency yielding a session, closed after the request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
