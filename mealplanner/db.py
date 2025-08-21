"""Database utilities for the Meals Planner Codex application."""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# SQLite engine configuration
ENGINE_URL = "sqlite:///data/app.db"
engine = create_engine(ENGINE_URL, future=True)

# Session factory
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

# Declarative base class
Base = declarative_base()


def init_db() -> None:
    """Initialize the database by creating all tables."""
    # Import models to ensure they are registered with SQLAlchemy's metadata.
    from . import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
