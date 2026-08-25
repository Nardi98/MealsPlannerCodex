"""Structured access logging.

With no error-tracking service wired up, Railway's log view is the only account
of what a tester actually hit when they report "it broke". One line per request
carrying method, path, status and duration makes that log answerable.
"""

import json
import logging
import sys

from fastapi.testclient import TestClient

import main
from main import app


def _records(caplog):
    return [r for r in caplog.records if r.name == main.ACCESS_LOGGER_NAME]


def test_a_request_emits_one_structured_line(caplog):
    with caplog.at_level(logging.INFO, logger=main.ACCESS_LOGGER_NAME):
        TestClient(app).get("/health")

    records = _records(caplog)
    assert len(records) == 1
    payload = json.loads(records[0].getMessage())
    assert payload["method"] == "GET"
    assert payload["path"] == "/health"
    assert payload["status"] == 200
    assert payload["duration_ms"] >= 0


def test_the_query_string_is_recorded_but_not_its_values(caplog):
    """Paths carry tokens -- ``/verify-email?token=...`` most obviously.

    Knowing *which* parameters were present is enough to reproduce a report;
    logging their values would persist credentials into the platform's log
    retention.
    """
    with caplog.at_level(logging.INFO, logger=main.ACCESS_LOGGER_NAME):
        TestClient(app).get("/health?token=super-secret&page=2")

    message = _records(caplog)[0].getMessage()
    assert "super-secret" not in message
    assert sorted(json.loads(message)["query_keys"]) == ["page", "token"]


def test_a_failing_request_is_logged_with_its_status(caplog):
    with caplog.at_level(logging.INFO, logger=main.ACCESS_LOGGER_NAME):
        TestClient(app).get("/definitely-not-a-route-abc123")

    payload = json.loads(_records(caplog)[0].getMessage())
    assert payload["status"] == 404


def test_non_http_scopes_are_passed_through(caplog):
    """Lifespan/websocket traffic is not a request and must not be logged."""
    with caplog.at_level(logging.INFO, logger=main.ACCESS_LOGGER_NAME):
        with TestClient(app):
            pass

    assert _records(caplog) == []


def test_the_access_logger_is_wired_to_stdout():
    """The middleware is useless if nothing is listening.

    Uvicorn configures its own loggers and leaves the root logger without a
    handler, so a logger that merely propagates emits nothing at all in the
    deployed container -- which is exactly where these lines are the only
    record of what happened.
    """
    logger = logging.getLogger(main.ACCESS_LOGGER_NAME)

    assert logger.isEnabledFor(logging.INFO)
    streams = [
        h.stream for h in logger.handlers if isinstance(h, logging.StreamHandler)
    ]
    assert sys.stdout in streams
