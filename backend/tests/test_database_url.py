"""Tests for env-driven database URL resolution in ``database.py``."""

import database


def test_defaults_to_sqlite_when_env_unset(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    url, connect_args = database.resolve_database_url()
    assert url.startswith("sqlite:///")
    assert url.endswith("app.db")
    assert connect_args == {"check_same_thread": False}


def test_uses_env_database_url_when_set(monkeypatch):
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql://user:pass@host:5432/mealsdb"
    )
    url, connect_args = database.resolve_database_url()
    assert url == "postgresql://user:pass@host:5432/mealsdb"
    assert connect_args == {}


def test_normalizes_bare_postgres_scheme(monkeypatch):
    monkeypatch.setenv(
        "DATABASE_URL", "postgres://user:pass@host:5432/mealsdb"
    )
    url, connect_args = database.resolve_database_url()
    assert url == "postgresql://user:pass@host:5432/mealsdb"
    assert connect_args == {}
