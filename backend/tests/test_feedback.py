"""Accept / reject feedback, at the domain layer and over the API.

- *Domain*: ``crud`` updates the score and the rejection date, by recipe id.
- *API*: the feedback endpoints identify the recipe by id (FR-13), log a
  ``feedback`` event, and never pick a replacement (S3) -- that is
  ``/meal-plans/replace``'s job. The meal-plan acceptance toggle round-trips.

Kept in one module so the two layers stay visibly paired; the section markers
below are the boundary.
"""

from __future__ import annotations

from datetime import date

import crud
from models import DevLogEntry

DAY = date(2024, 1, 1)


# ---------------------------------------------------------------------------
# Domain layer
# ---------------------------------------------------------------------------
def test_accept_recipe_bumps_the_score(db_session):
    r = crud.create_recipe(db_session, title="Test", course="main", score=0)
    crud.accept_recipe(db_session, r.id)
    db_session.refresh(r)
    assert r.score == 1


def test_accepting_a_leftover_does_not_bump_the_score(db_session):
    """Q7: one batch counts as one accept."""
    r = crud.create_recipe(db_session, title="Batch", course="main", score=0)
    assert crud.accept_recipe(db_session, r.id, leftover=True) is r
    db_session.refresh(r)
    assert r.score == 0


def test_reject_recipe_drops_the_score_and_stamps_the_slot_date(db_session):
    r = crud.create_recipe(db_session, title="Test2", course="main", score=0)
    crud.reject_recipe(db_session, r.id, DAY)
    db_session.refresh(r)
    assert r.score == -1
    assert r.date_last_rejected == DAY


def test_accept_recipe_leaves_date_last_rejected(db_session):
    r = crud.create_recipe(db_session, title="AcceptKeep", course="main", score=0)
    crud.accept_recipe(db_session, r.id)
    db_session.refresh(r)
    assert r.date_last_rejected is None


def test_feedback_on_a_duplicate_title_touches_only_that_id(db_session):
    r1 = crud.create_recipe(db_session, title="Dup", course="main", score=0)
    r2 = crud.create_recipe(db_session, title="Dup", course="main", score=0)

    crud.accept_recipe(db_session, r2.id)

    db_session.refresh(r1)
    db_session.refresh(r2)
    assert (r1.score, r2.score) == (0, 1)


def test_feedback_on_someone_elses_recipe_finds_nothing(db_session, user, other_user):
    theirs = crud.create_recipe(db_session, title="T", course="main", user_id=other_user.id)
    assert crud.accept_recipe(db_session, theirs.id, user_id=user.id) is None
    assert crud.reject_recipe(db_session, theirs.id, DAY, user_id=user.id) is None


# ---------------------------------------------------------------------------
# API layer
# ---------------------------------------------------------------------------
def _feedback_events(db_session, user):
    return [
        e.payload
        for e in db_session.query(DevLogEntry).filter_by(user_id=user.id, event="feedback")
    ]


def test_accept_endpoint_bumps_and_logs(db_session, user, auth_client):
    a = crud.create_recipe(db_session, title="A", course="main", score=0, user_id=user.id)

    resp = auth_client.post(
        "/feedback/accept", json={"recipe_id": a.id, "plan_date": DAY.isoformat()}
    )

    assert resp.status_code == 200
    db_session.refresh(a)
    assert a.score == 1
    assert _feedback_events(db_session, user) == [{
        "kind": "accept", "recipe_id": a.id, "plan_date": DAY.isoformat(),
        "leftover": False, "score": 1.0,
    }]


def test_accepting_a_leftover_over_the_api_does_not_bump(db_session, user, auth_client):
    a = crud.create_recipe(db_session, title="A", course="main", score=0, user_id=user.id)

    resp = auth_client.post(
        "/feedback/accept",
        json={"recipe_id": a.id, "plan_date": DAY.isoformat(), "leftover": True},
    )

    assert resp.status_code == 200
    db_session.refresh(a)
    assert a.score == 0


def test_reject_endpoint_bans_from_the_slot_date_and_suggests_nothing(
    db_session, user, auth_client
):
    a = crud.create_recipe(db_session, title="A", course="main", score=0, user_id=user.id)
    crud.create_recipe(db_session, title="B", course="main", score=0, user_id=user.id)

    resp = auth_client.post(
        "/feedback/reject", json={"recipe_id": a.id, "plan_date": DAY.isoformat()}
    )

    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
    db_session.refresh(a)
    assert (a.score, a.date_last_rejected) == (-1, DAY)
    assert _feedback_events(db_session, user)[0]["kind"] == "reject"


def test_feedback_on_an_unknown_id_is_404(auth_client):
    for kind in ("accept", "reject"):
        resp = auth_client.post(
            f"/feedback/{kind}", json={"recipe_id": 10**9, "plan_date": DAY.isoformat()}
        )
        assert resp.status_code == 404


def test_toggle_meal_acceptance(db_session, user, auth_client):
    r = crud.create_recipe(db_session, user_id=user.id, title="A", course="main")
    crud.set_meal_plan(db_session, {DAY.isoformat(): [r.id]}, user.id)
    client = auth_client
    expected = {
        "recipe": "A",
        "recipe_id": r.id,
        "side_recipes": [],
        "side_recipe_ids": [],
        "accepted": True,
        "leftover": False,
        "meal_number": 1,
        "people": 2,
    }

    resp = client.post(
        "/meal-plans/accept",
        json={"plan_date": "2024-01-01", "meal_number": 1, "accepted": True},
    )
    assert resp.status_code == 200
    assert resp.json() == expected

    resp2 = client.get("/meal-plans", params={"plan_date": "2024-01-01"})
    assert resp2.status_code == 200
    assert resp2.json() == {"2024-01-01": [expected]}
