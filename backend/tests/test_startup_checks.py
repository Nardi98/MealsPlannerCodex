"""Tests for startup schema verification logic."""

import sys
from pathlib import Path

import pytest
from sqlalchemy.exc import OperationalError

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import backend.main as main


class _DummyInspector:
    def has_table(self, name: str) -> bool:
        return True


class _MissingInspector:
    def __init__(self, missing: set[str]):
        self._missing = missing

    def has_table(self, name: str) -> bool:  # pragma: no cover - simple data holder
        return name not in self._missing


def _operational_error() -> OperationalError:
    return OperationalError("SELECT 1", {}, Exception("boom"))


class _FakePgError:
    def __init__(self, pgcode: str | None, message: str):
        self.pgcode = pgcode
        self._message = message

    def __str__(self) -> str:  # pragma: no cover - trivial accessor
        return self._message


def test_verify_schema_retries_until_success(monkeypatch):
    attempts = 0

    def fake_inspect(_engine):
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise _operational_error()
        return _DummyInspector()

    monkeypatch.setattr(main, "inspect", fake_inspect)
    monkeypatch.setattr(main, "_STARTUP_RETRY_ATTEMPTS", 5, raising=False)
    monkeypatch.setattr(main, "_STARTUP_RETRY_DELAY", 0, raising=False)

    main._verify_schema_state()

    assert attempts == 3


def test_verify_schema_raises_after_max_attempts(monkeypatch):
    def fake_inspect(_engine):
        raise _operational_error()

    monkeypatch.setattr(main, "inspect", fake_inspect)
    monkeypatch.setattr(main, "_STARTUP_RETRY_ATTEMPTS", 2, raising=False)
    monkeypatch.setattr(main, "_STARTUP_RETRY_DELAY", 0, raising=False)

    with pytest.raises(RuntimeError) as excinfo:
        main._verify_schema_state()

    assert "Unable to connect to the configured database" in str(excinfo.value)


def test_verify_schema_creates_missing_tables(monkeypatch):
    called = {}

    def fake_run_migrations(url):
        called["ran"] = url

    monkeypatch.setattr(main, "run_migrations", fake_run_migrations)
    monkeypatch.setattr(main, "_await_database_ready", lambda: _MissingInspector({"recipes"}))

    main._verify_schema_state()

    assert called.get("ran") == main.DATABASE_URL


def test_verify_schema_creates_database(monkeypatch):
    created = {}

    def fake_inspect(_engine):
        if "error" not in created:
            created["error"] = True
            raise _operational_error()
        return _MissingInspector({"recipes"})

    def fake_attempt_create_database(error):
        created["database"] = True
        return True

    monkeypatch.setattr(main, "inspect", fake_inspect)
    monkeypatch.setattr(main, "_attempt_create_database", fake_attempt_create_database)
    monkeypatch.setattr(main, "run_migrations", lambda url: created.setdefault("tables", True))

    main._verify_schema_state()

    assert created["database"] is True
    assert created["tables"] is True


def test_attempt_create_database_ignored_for_unrelated_error(monkeypatch):
    error = OperationalError("SELECT 1", {}, _FakePgError("42883", "function missing"))
    monkeypatch.setattr(
        main, "DATABASE_URL", "postgresql+psycopg2://user:pass@host/dbname", raising=False
    )

    assert main._attempt_create_database(error) is False


def test_attempt_create_database_creates(monkeypatch):
    created = {}

    class DummyConn:
        dialect = type(
            "_Dialect",
            (),
            {"identifier_preparer": type("_Prep", (), {"quote": staticmethod(lambda value: f'"{value}"')})()},
        )()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def exec_driver_sql(self, statement):
            created["sql"] = statement

    class DummyEngine:
        def connect(self):
            created["connected"] = True
            return DummyConn()

        def dispose(self):
            created["disposed"] = True

    orig_error = _FakePgError("3D000", "database does not exist")
    error = OperationalError("SELECT 1", {}, orig_error)

    monkeypatch.setattr(main, "DATABASE_URL", "postgresql+psycopg2://user:pass@host/dbname", raising=False)
    monkeypatch.setattr(main, "create_engine", lambda url, **kwargs: DummyEngine())

    assert main._attempt_create_database(error) is True
    assert created["connected"] is True
    assert created["disposed"] is True
    assert created["sql"] == 'CREATE DATABASE "dbname"'
