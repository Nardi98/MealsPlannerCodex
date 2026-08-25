"""``/health``: the liveness probe Railway polls.

Deliberately does not touch the database. A healthcheck that fails on a
transient DB blip makes the platform kill and restart an otherwise healthy
container, turning a brief upstream hiccup into an outage.
"""

from fastapi.testclient import TestClient

import models
from database import get_db
from main import app


def test_health_is_200_and_needs_no_auth():
    # A bare client with no dependency overrides: nothing is wired to a
    # database here, which is exactly the point.
    resp = TestClient(app).get("/health")

    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_health_declares_no_database_dependency():
    """The probe must stay a pure liveness check.

    Asserted against the route's resolved dependency tree rather than by
    monkeypatching ``SessionLocal``: the handler binds nothing from
    ``database``, so a patch there would be unobserved and the test would pass
    just as happily after the regression it claims to guard.
    """
    route = next(r for r in app.routes if getattr(r, "path", None) == "/health")

    calls = [d.call for d in route.dependant.dependencies]
    assert get_db not in calls
    assert route.dependant.dependencies == []


def test_health_is_a_reserved_username():
    """Otherwise a user could claim the handle ``health`` and shadow the probe."""
    assert "health" in models.RESERVED_USERNAMES
