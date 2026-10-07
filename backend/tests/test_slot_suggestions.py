"""Single-slot suggestions: replacing a main and adding a side (FR-1, FR-11, S1).

Both paths run the same engine as weekly generation, against the saved plan
around the slot, and both stamp ``date_last_suggested`` and log the trace.
"""

from datetime import date, timedelta

import pytest

import crud
from models import DevLogEntry, Ingredient, RecipeIngredient, Tag
from tests.conftest import client_as

DAY = date(2025, 3, 10)


@pytest.fixture
def mains(db_session, user):
    """Three mains whose base scores rank them A > B > C."""
    return [
        crud.create_recipe(db_session, title=t, course="main", score=s, user_id=user.id)
        for t, s in (("A", 5.0), ("B", 3.0), ("C", 1.0))
    ]


def _plan(db_session, user, days):
    crud.set_meal_plan(
        db_session, {d.isoformat(): [r.id for r in rs] for d, rs in days.items()}, user.id
    )


def _replace(client, exclude, day=DAY, meal_number=1, **extra):
    return client.post(
        "/meal-plans/replace",
        json={"plan_date": day.isoformat(), "meal_number": meal_number,
              "exclude_ids": [r.id for r in exclude], **extra},
    )


# --------------------------------------------------------------------------
# Replacing a main
# --------------------------------------------------------------------------
def test_replace_returns_the_best_other_main_for_the_slot(auth_client, db_session, user, mains):
    a, b, _c = mains
    _plan(db_session, user, {DAY: [a]})

    resp = _replace(auth_client, [a])

    assert resp.status_code == 200
    assert resp.json() == {"id": b.id, "title": "B"}


def test_replace_never_returns_an_excluded_id(auth_client, db_session, user, mains):
    a, b, c = mains
    _plan(db_session, user, {DAY: [a]})

    assert _replace(auth_client, [a, b]).json()["id"] == c.id
    assert _replace(auth_client, [a, b, c]).status_code == 400


def test_replace_respects_the_ban(auth_client, db_session, user, mains):
    a, b, c = mains
    b.date_last_rejected = DAY - timedelta(days=1)
    _plan(db_session, user, {DAY: [a]})

    assert _replace(auth_client, [a]).json()["id"] == c.id


def test_replace_respects_the_season(auth_client, db_session, user, mains):
    a, b, c = mains
    summer = Ingredient(name="summer-veg", season_months=[7], user_id=user.id)
    b.ingredients = [RecipeIngredient(ingredient=summer, recipe=b)]
    _plan(db_session, user, {DAY: [a]})

    assert _replace(auth_client, [a]).json()["id"] == c.id


def test_replace_respects_avoid_tags(auth_client, db_session, user, mains):
    a, b, c = mains
    b.tags = [Tag(name="fried", user_id=user.id)]
    _plan(db_session, user, {DAY: [a]})

    assert _replace(auth_client, [a], avoid_tags=["fried"]).json()["id"] == c.id


def test_replace_respects_the_rest_of_the_plan(auth_client, db_session, user, mains):
    """B is already planned two days later, inside the 5-day minimum gap."""
    a, b, c = mains
    _plan(db_session, user, {DAY: [a], DAY + timedelta(days=2): [b]})

    assert _replace(auth_client, [a]).json()["id"] == c.id


def test_reject_ping_pong_never_brings_the_first_dish_back(auth_client, db_session, user, mains):
    """Reject A -> B; reject B -> not A, even when the client forgets A was excluded."""
    a, b, c = mains
    crud.create_recipe(db_session, title="D", course="main", score=0.5, user_id=user.id)
    _plan(db_session, user, {DAY: [a]})

    auth_client.post("/feedback/reject", json={"recipe_id": a.id, "plan_date": DAY.isoformat()})
    assert _replace(auth_client, [a]).json()["id"] == b.id
    _plan(db_session, user, {DAY: [b]})

    auth_client.post("/feedback/reject", json={"recipe_id": b.id, "plan_date": DAY.isoformat()})
    assert _replace(auth_client, [b]).json()["id"] == c.id
    # A stays banned for the rest of its 4-day window, on any slot.
    for offset in (1, 3):
        later = DAY + timedelta(days=offset)
        assert _replace(auth_client, [c], day=later).json()["id"] != a.id


def test_replace_stamps_the_suggestion_and_logs_it(auth_client, db_session, user, mains):
    a, b, _c = mains
    _plan(db_session, user, {DAY: [a]})

    _replace(auth_client, [a], meal_number=1)

    db_session.refresh(b)
    assert b.date_last_suggested == DAY
    [entry] = db_session.query(DevLogEntry).filter_by(user_id=user.id).all()
    assert (entry.channel, entry.event) == ("planner", "replace_main")
    assert entry.payload["slot"]["chosen"]["id"] == b.id
    assert entry.payload["exclude_ids"] == [a.id]


def test_replace_only_draws_on_the_callers_recipes(db_session, user, other_user, mains):
    a, b, _c = mains
    crud.create_recipe(db_session, title="Theirs", course="main", score=99.0,
                       user_id=other_user.id)
    _plan(db_session, user, {DAY: [a]})
    from main import app

    try:
        assert _replace(client_as(db_session, user), [a]).json()["id"] == b.id
    finally:
        app.dependency_overrides.clear()


# --------------------------------------------------------------------------
# Adding a side
# --------------------------------------------------------------------------
@pytest.fixture
def sides(db_session, user):
    return [
        crud.create_recipe(db_session, title=t, course="side", score=s, user_id=user.id)
        for t, s in (("S1", 3.0), ("S2", 2.0), ("S3", 1.0))
    ]


def _side(client, day, meal_number=1, **extra):
    return client.post(
        "/side-dishes/generate",
        json={"plan_date": day.isoformat(), "meal_number": meal_number, **extra},
    )


def test_side_suggestions_differ_across_days_of_the_same_week(
    auth_client, db_session, user, mains, sides
):
    """S1: each suggestion is scored against its meal's date, so recency bites."""
    days = [DAY + timedelta(days=i) for i in range(3)]
    _plan(db_session, user, {d: [mains[0]] for d in days})

    picked = []
    for d in days:
        side_id = _side(auth_client, d).json()["id"]
        crud.add_meal_side(db_session, d, 1, side_id, user.id)
        picked.append(side_id)

    assert len(set(picked)) == 3


def test_a_side_already_on_the_plate_is_not_suggested(auth_client, db_session, user, mains, sides):
    s1, s2, _s3 = sides
    _plan(db_session, user, {DAY: [mains[0]]})
    crud.add_meal_side(db_session, DAY, 1, s1.id, user.id)

    assert _side(auth_client, DAY, epsilon=0.0).json()["id"] == s2.id


def test_side_suggestions_honour_exclusions_and_the_ban(
    auth_client, db_session, user, mains, sides
):
    s1, s2, s3 = sides
    s2.date_last_rejected = DAY
    _plan(db_session, user, {DAY: [mains[0]]})

    resp = _side(auth_client, DAY, epsilon=0.0, exclude_ids=[s1.id])

    assert resp.json() == {"id": s3.id, "title": "S3"}


def test_side_suggestion_stamps_and_logs(auth_client, db_session, user, mains, sides):
    s1 = sides[0]
    _plan(db_session, user, {DAY: [mains[0]]})

    _side(auth_client, DAY, epsilon=0.0)

    db_session.refresh(s1)
    assert s1.date_last_suggested == DAY
    [entry] = db_session.query(DevLogEntry).filter_by(user_id=user.id).all()
    assert (entry.channel, entry.event) == ("planner", "suggest_side")
    assert entry.payload["slot"]["chosen"]["id"] == s1.id


def test_side_suggestions_default_to_some_exploration():
    from schemas import SideDishGenerate

    assert SideDishGenerate(plan_date=DAY, meal_number=1).epsilon == 0.25
