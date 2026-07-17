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
        == "postgresql://user:pass@host:5432/mealsdb"
    )


def test_normalizes_bare_postgres_scheme(monkeypatch):
    monkeypatch.setenv(
        "DATABASE_URL", "postgres://user:pass@host:5432/mealsdb"
    )
    assert (
        database.resolve_database_url()
        == "postgresql://user:pass@host:5432/mealsdb"
    )
