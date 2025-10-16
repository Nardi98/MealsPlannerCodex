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


def _operational_error() -> OperationalError:
    return OperationalError("SELECT 1", {}, Exception("boom"))


def test_verify_schema_retries_until_success(monkeypatch):
    attempts = 0

    def fake_inspect(_engine):
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise _operational_error()
        return _DummyInspector()

    monkeypatch.setattr(main, "USING_DEV_FALLBACK", False, raising=False)
    monkeypatch.setattr(main, "inspect", fake_inspect)
    monkeypatch.setattr(main, "_STARTUP_RETRY_ATTEMPTS", 5, raising=False)
    monkeypatch.setattr(main, "_STARTUP_RETRY_DELAY", 0, raising=False)

    main._verify_schema_state()

    assert attempts == 3


def test_verify_schema_raises_after_max_attempts(monkeypatch):
    def fake_inspect(_engine):
        raise _operational_error()

    monkeypatch.setattr(main, "USING_DEV_FALLBACK", False, raising=False)
    monkeypatch.setattr(main, "inspect", fake_inspect)
    monkeypatch.setattr(main, "_STARTUP_RETRY_ATTEMPTS", 2, raising=False)
    monkeypatch.setattr(main, "_STARTUP_RETRY_DELAY", 0, raising=False)

    with pytest.raises(RuntimeError) as excinfo:
        main._verify_schema_state()

    assert "Unable to connect to the configured database" in str(excinfo.value)


def test_verify_schema_uses_sqlite_fallback(monkeypatch):
    called = {}

    def fake_create_all(*args, **kwargs):
        called["ran"] = True

    monkeypatch.setattr(main.models.Base.metadata, "create_all", fake_create_all)
    monkeypatch.setattr(main, "USING_DEV_FALLBACK", True, raising=False)

    main._verify_schema_state()

    assert called.get("ran") is True
