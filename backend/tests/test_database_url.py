"""Tests for env-driven database URL resolution in ``database.py``."""

import pytest

import database


def test_raises_when_database_url_unset(monkeypatch):
    """No fallback: an unset DATABASE_URL must fail loudly, not guess.

    On Railway a missing variable reference would otherwise boot the app on a
    throwaway local database that silently drops every write on redeploy.
    """
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        database.resolve_database_url()


def test_uses_env_database_url_when_set(monkeypatch):
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql://user:pass@host:5432/mealsdb"
    )
    assert (
        database.resolve_database_url()
        == "postgresql+psycopg2://user:pass@host:5432/mealsdb"
    )


def test_normalizes_bare_postgres_scheme(monkeypatch):
    monkeypatch.setenv(
        "DATABASE_URL", "postgres://user:pass@host:5432/mealsdb"
    )
    assert (
        database.resolve_database_url()
        == "postgresql+psycopg2://user:pass@host:5432/mealsdb"
    )


def test_names_the_psycopg2_driver_explicitly(monkeypatch):
    """A bare URL must not be left to SQLAlchemy's default DBAPI.

    SQLAlchemy 2.1 changed that default from ``psycopg2`` to ``psycopg`` (v3),
    which this image does not install: an unpinned rebuild died at import with
    ``ModuleNotFoundError: No module named 'psycopg'``. Naming the driver keeps
    the app, Alembic and every deployment on the one that is installed.
    """
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql://user:pass@host:5432/mealsdb"
    )
    assert database.resolve_database_url().startswith("postgresql+psycopg2://")


def test_an_explicit_driver_is_left_alone(monkeypatch):
    """Naming a driver is the caller's prerogative; do not rewrite it."""
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql+psycopg://user:pass@host:5432/mealsdb"
    )
    assert (
        database.resolve_database_url()
        == "postgresql+psycopg://user:pass@host:5432/mealsdb"
    )
