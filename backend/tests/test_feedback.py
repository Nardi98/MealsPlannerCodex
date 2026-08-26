"""Accept / reject feedback, at the domain layer and over the API.

- *Domain*: ``crud`` updates the score and the last-consumed / last-rejected
  dates directly.
- *API*: the feedback endpoints hand back a unique replacement, and the
  meal-plan acceptance toggle round-trips.

Kept in one module so the two layers stay visibly paired; the section markers
below are the boundary.
"""

from __future__ import annotations

from datetime import date

import crud


# ---------------------------------------------------------------------------
# Domain layer
# ---------------------------------------------------------------------------
def test_accept_recipe_updates_score_and_date(db_session):
    r = crud.create_recipe(
        db_session,
        title="Test",
        course="main",
        score=0,
    )
    consumed = date(2024, 1, 1)
    crud.accept_recipe(db_session, "Test", consumed)
    db_session.refresh(r)
    assert r.score == 1
    assert r.date_last_consumed == consumed


def test_reject_recipe_updates_score(db_session):
    r = crud.create_recipe(
        db_session,
        title="Test2",
        course="main",
        score=0,
    )
    crud.reject_recipe(db_session, "Test2")
    db_session.refresh(r)
    assert r.score == -1
    assert r.date_last_consumed is None


def test_reject_recipe_stamps_date_last_rejected(db_session):
    """Rejecting a recipe records the day so exploration can measure staleness."""

    r = crud.create_recipe(
        db_session,
        title="RejectStamp",
        course="main",
        score=0,
    )
    assert r.date_last_rejected is None
    crud.reject_recipe(db_session, "RejectStamp")
    db_session.refresh(r)
    assert r.date_last_rejected == date.today()


def test_accept_recipe_leaves_date_last_rejected(db_session):
    """Accepting must not reset the staleness anchor (accept preserves it)."""

    r = crud.create_recipe(
        db_session,
        title="AcceptKeep",
        course="main",
        score=0,
    )
    crud.accept_recipe(db_session, "AcceptKeep", date(2024, 1, 1))
    db_session.refresh(r)
    assert r.date_last_rejected is None


def test_accept_recipe_handles_duplicates(db_session):
    """Accepting a recipe with a non-unique title updates only one entry."""

    r1 = crud.create_recipe(db_session, title="Dup", course="main", score=0)
    r2 = crud.create_recipe(db_session, title="Dup", course="main", score=0)

    # Should not raise MultipleResultsFound even with duplicate titles
    consumed = date(2024, 2, 2)
    crud.accept_recipe(db_session, "Dup", consumed)

    db_session.refresh(r1)
    db_session.refresh(r2)

    scores = {r1.score, r2.score}
    dates = {r1.date_last_consumed, r2.date_last_consumed}
    assert scores == {0, 1}
    assert dates == {None, consumed}


# ---------------------------------------------------------------------------
# API layer
# ---------------------------------------------------------------------------
def test_feedback_endpoints_return_unique_replacement(db_session, user, auth_client):
    client = auth_client
    uid = user.id
    a = crud.create_recipe(db_session, title="A", course="main", score=0, user_id=uid)
    crud.create_recipe(db_session, title="B", course="main", score=0, user_id=uid)
    c = crud.create_recipe(db_session, title="C", course="main", score=0, user_id=uid)
    crud.set_meal_plan(
        db_session,
        {
            "2024-01-01": [
                {"main_id": a.id, "leftover": False},
                {"main_id": c.id, "leftover": True},
            ]
        },
        uid,
    )

    consumed = date(2024, 1, 1)
    resp = client.post(
        "/feedback/accept", json={"title": "A", "consumed_date": consumed.isoformat()}
    )
    assert resp.status_code == 200
    db_session.refresh(a)
    assert a.score == 1
    assert a.date_last_consumed == consumed

    resp = client.post(
        "/feedback/reject", json={"title": "A", "consumed_date": consumed.isoformat()}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["replacement"] == "B"


def test_reject_replacement_limited_to_main_courses(db_session, user, auth_client):
    client = auth_client
    uid = user.id
    a = crud.create_recipe(db_session, title="A", course="main", score=0, user_id=uid)
    crud.create_recipe(db_session, title="B", course="main", score=0, user_id=uid)
    crud.create_recipe(
        db_session, title="C", course="dessert", score=0, user_id=uid
    )
    crud.set_meal_plan(
        db_session,
        {"2024-01-01": [{"main_id": a.id, "leftover": False}]},
        uid,
    )

    consumed = date(2024, 1, 1)
    resp = client.post(
        "/feedback/reject", json={"title": "A", "consumed_date": consumed.isoformat()}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["replacement"] == "B"
    assert data["replacement"] != "C"


def test_toggle_meal_acceptance(db_session, user, auth_client):
    r = crud.create_recipe(db_session, user_id=user.id, title="A", course="main")
    plan_date = date(2024, 1, 1)
    crud.set_meal_plan(db_session, {plan_date.isoformat(): [r.id]}, user.id)
    client = auth_client

    resp = client.post(
        "/meal-plans/accept",
        json={"plan_date": "2024-01-01", "meal_number": 1, "accepted": True},
    )
    assert resp.status_code == 200
    assert resp.json() == {
        "recipe": "A",
        "side_recipes": [],
        "accepted": True,
        "leftover": False,
        "meal_number": 1,
        "people": 2,
    }

    resp2 = client.get("/plan", params={"plan_date": "2024-01-01"})
    assert resp2.status_code == 200
    assert resp2.json() == {
        "2024-01-01": [
            {
                "recipe": "A",
                "side_recipes": [],
                "accepted": True,
                "leftover": False,
                "meal_number": 1,
                "people": 2,
            }
        ]
    }
