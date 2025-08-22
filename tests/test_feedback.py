"""Tests for accepting and rejecting recipes."""

from __future__ import annotations

from datetime import date

from mealplanner import crud


def test_accept_recipe_updates_score_and_date(db_session):
    r = crud.create_recipe(
        db_session,
        title="Test",
        servings_default=1,
        score=0,
    )
    crud.accept_recipe(db_session, "Test")
    db_session.refresh(r)
    assert r.score == 1
    assert r.date_last_consumed == date.today()


def test_reject_recipe_updates_score(db_session):
    r = crud.create_recipe(
        db_session,
        title="Test2",
        servings_default=1,
        score=0,
    )
    crud.reject_recipe(db_session, "Test2")
    db_session.refresh(r)
    assert r.score == -1
    assert r.date_last_consumed is None

