"""Database utilities for the Meals Planner Codex application."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# SQLAlchemy database URL for the application. Uses a SQLite file stored under
# the backend's ``data`` directory.  Build an absolute path so tests and the
# app behave the same regardless of the current working directory.
_BASE_DIR = Path(__file__).resolve().parent
DATABASE_URL = f"sqlite:///{_BASE_DIR / 'data' / 'app.db'}"

# Create the core SQLAlchemy engine and session factory. ``future=True`` enables
# 2.0 style usage which is what this project is targeting.
engine = create_engine(DATABASE_URL, future=True)

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
