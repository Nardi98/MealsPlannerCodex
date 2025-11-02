"""Tests for accepting and rejecting recipes."""

from __future__ import annotations

from datetime import date
from uuid import uuid4

from mealplanner import crud


def test_accept_recipe_updates_score_and_date(db_session):
    r = crud.create_recipe(
        db_session,
        title="Test",
        servings_default=1,
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
        servings_default=1,
        course="main",
        score=0,
    )
    crud.reject_recipe(db_session, "Test2")
    db_session.refresh(r)
    assert r.score == -1
    assert r.date_last_consumed is None


def test_accept_recipe_handles_duplicates(db_session):
    """Accepting a recipe with a non-unique title updates only one entry."""

    r1 = crud.create_recipe(db_session, title="Dup", servings_default=1, course="main", score=0)
    r2 = crud.create_recipe(db_session, title="Dup", servings_default=1, course="main", score=0)

    # Should not raise MultipleResultsFound even with duplicate titles
    consumed = date(2024, 2, 2)
    crud.accept_recipe(db_session, "Dup", consumed)

    db_session.refresh(r1)
    db_session.refresh(r2)

    scores = {r1.score, r2.score}
    dates = {r1.date_last_consumed, r2.date_last_consumed}
    assert scores == {0, 1}
    assert dates == {None, consumed}


def test_feedback_isolated_by_user(db_session):
    suffix1 = uuid4().hex
    suffix2 = uuid4().hex
    user1 = crud.create_user(
        db_session,
        email=f"feedback-{suffix1}@example.com",
        username=f"feedback-{suffix1}",
        password="Password123!",
    )
    user2 = crud.create_user(
        db_session,
        email=f"feedback-{suffix2}@example.com",
        username=f"feedback-{suffix2}",
        password="Password123!",
    )

    r1 = crud.create_recipe(
        db_session,
        title="Shared",
        servings_default=1,
        course="main",
        score=0,
        user=user1,
    )
    r2 = crud.create_recipe(
        db_session,
        title="Shared",
        servings_default=1,
        course="main",
        score=0,
        user=user2,
    )

    consumed = date(2024, 3, 1)
    crud.accept_recipe(db_session, "Shared", consumed, user=user1)
    db_session.refresh(r1)
    db_session.refresh(r2)
    assert r1.score == 1 and r1.date_last_consumed == consumed
    assert r2.score == 0 and r2.date_last_consumed is None

    crud.reject_recipe(db_session, "Shared", user=user2)
    db_session.refresh(r1)
    db_session.refresh(r2)
    assert r1.score == 1
    assert r2.score == -1

