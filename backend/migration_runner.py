"""Utilities for executing Alembic migrations programmatically."""
from __future__ import annotations

from pathlib import Path
from typing import Optional, Union

from alembic import command
from alembic.config import Config
from sqlalchemy.engine import Connection, Engine

BASE_DIR = Path(__file__).resolve().parent

BindArg = Union[str, Engine, Connection]


def _alembic_config(database_url: Optional[str] = None) -> Config:
    config = Config(str(BASE_DIR / "alembic.ini"))
    script_location = BASE_DIR / "alembic"
    config.set_main_option("script_location", str(script_location))
    config.attributes["configure_logger"] = False
    if database_url:
        config.set_main_option("sqlalchemy.url", database_url)
    return config


def upgrade(bind: Optional[BindArg] = None, revision: str = "head") -> None:
    """Apply Alembic migrations up to ``revision`` for the given database handle."""

    connection: Connection | None = None
    close_connection = False
    database_url: Optional[str] = None

    if isinstance(bind, Engine):
        connection = bind.connect()
        close_connection = True
        database_url = str(bind.url)
    elif isinstance(bind, Connection):
        connection = bind
        engine = getattr(connection, "engine", None)
        if engine is not None:
            database_url = str(engine.url)
    elif bind is not None:
        database_url = str(bind)

    config = _alembic_config(database_url)
    try:
        if connection is not None:
            config.attributes["connection"] = connection
        command.upgrade(config, revision)
    finally:
        if close_connection and connection is not None:
            connection.close()


__all__ = ["upgrade"]
