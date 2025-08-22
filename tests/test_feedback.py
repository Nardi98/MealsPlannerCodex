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


def test_accept_recipe_handles_duplicates(db_session):
    """Accepting a recipe with a non-unique title updates only one entry."""

    r1 = crud.create_recipe(db_session, title="Dup", servings_default=1, score=0)
    r2 = crud.create_recipe(db_session, title="Dup", servings_default=1, score=0)

    # Should not raise MultipleResultsFound even with duplicate titles
    crud.accept_recipe(db_session, "Dup")

    db_session.refresh(r1)
    db_session.refresh(r2)

    scores = {r1.score, r2.score}
    dates = {r1.date_last_consumed, r2.date_last_consumed}
    assert scores == {0, 1}
    assert dates == {None, date.today()}

