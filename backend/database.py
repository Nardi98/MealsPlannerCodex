"""Database utilities for the Meals Planner Codex application."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, text, inspect
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


def _ensure_course_column() -> None:
    """Add the ``course`` column to the ``recipes`` table if missing."""

    inspector = inspect(engine)
    columns = [col["name"] for col in inspector.get_columns("recipes")]
    if "course" in columns:
        return
    with engine.begin() as conn:
        conn.execute(
            text(
                "ALTER TABLE recipes ADD COLUMN course VARCHAR NOT NULL DEFAULT 'MAIN_DISH'"
            )
        )


def init_db() -> None:
    """Create or upgrade database schema.

    Ensures all tables exist and performs simple migrations for older
    databases. Safe to call multiple times; existing data is left intact.
    """

    Base.metadata.create_all(bind=engine)
    if engine.url.database != ":memory:":
        _ensure_course_column()
