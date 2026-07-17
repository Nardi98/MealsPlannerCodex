"""Leftover meals are linked to their bulk source and cascade-removed with it.

A leftover meal is defined by pointing at the source meal that produced it
(``leftover_source_date`` / ``leftover_source_meal``) rather than by a stored
boolean. Removing the source (e.g. rejecting the bulk meal) must remove the
orphaned leftovers automatically.
"""

from datetime import date

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

import crud
from models import Meal, MealPlan


D1 = "2024-01-01"
D2 = "2024-01-02"
D3 = "2024-01-03"


def _bulk_plan(session, user):
    """Create a bulk source on D1 with leftovers on D2/D3 (same recipe)."""
    bulk = crud.create_recipe(
        session, title="Bulk", servings_default=1, course="main", bulk_prep=True,
        user_id=user.id
    )
    other = crud.create_recipe(
        session, title="Other", servings_default=1, course="main", user_id=user.id
    )
    crud.set_meal_plan(
        session,
        {
            D1: [{"main_id": bulk.id, "leftover": False}],
            D2: [{"main_id": bulk.id, "leftover": True}],
            D3: [{"main_id": bulk.id, "leftover": True}],
        },
        user.id,
    )
    return bulk, other


def _meal(session, user, day):
    return session.get(Meal, (user.id, date.fromisoformat(day), 1))


def test_set_meal_plan_links_leftovers_to_source(db_session, user):
    _bulk_plan(db_session, user)

    source = _meal(db_session, user, D1)
    lo2 = _meal(db_session, user, D2)
    lo3 = _meal(db_session, user, D3)

    # Source keeps both link columns NULL and is not a leftover.
    assert source.leftover_source_date is None
    assert source.leftover_source_meal is None
    assert source.leftover is False

    # Leftovers point at the source PK and report leftover=True.
    for lo in (lo2, lo3):
        assert lo.leftover_source_date == date.fromisoformat(D1)
        assert lo.leftover_source_meal == 1
        assert lo.leftover is True


def test_check_constraint_rejects_half_populated_link(db_session, user):
    db_session.add(MealPlan(user_id=user.id, plan_date=date.fromisoformat(D1)))
    db_session.flush()
    # Only one of the two source columns set -> must violate the CHECK.
    db_session.add(
        Meal(
            user_id=user.id,
            plan_date=date.fromisoformat(D1),
            meal_number=1,
            recipe_id=None,
            leftover_source_date=date.fromisoformat(D1),
            leftover_source_meal=None,
        )
    )
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_remove_leftovers_for_source_deletes_only_linked(db_session, user):
    _bulk_plan(db_session, user)

    crud.remove_leftovers_for_source(db_session, date.fromisoformat(D1), 1, user.id)

    remaining = db_session.execute(select(Meal)).scalars().all()
    remaining_dates = {m.plan_date for m in remaining}
    assert date.fromisoformat(D1) in remaining_dates
    assert date.fromisoformat(D2) not in remaining_dates
    assert date.fromisoformat(D3) not in remaining_dates


def test_rejecting_bulk_source_removes_its_leftovers(db_session, user):
    """Re-persisting the source day with a different recipe drops the leftovers."""
    _bulk, other = _bulk_plan(db_session, user)

    # Simulate Reject: source day is re-persisted with a different (non-bulk) recipe.
    crud.set_meal_plan(
        db_session, {D1: [{"main_id": other.id, "leftover": False}]}, user.id
    )

    plan = crud.get_plan(
        db_session,
        start_date=date.fromisoformat(D1),
        end_date=date.fromisoformat(D3),
        user_id=user.id,
    )
    # Day 1 now holds the replacement; days 2 & 3 leftovers are gone.
    assert plan[D1][0]["recipe"] == "Other"
    assert plan.get(D2, []) == []
    assert plan.get(D3, []) == []


def test_rejecting_a_leftover_clears_its_leftover_link(db_session, user):
    """Re-persisting a leftover's day as a non-leftover clears the stale link."""
    _bulk, other = _bulk_plan(db_session, user)

    crud.set_meal_plan(
        db_session, {D2: [{"main_id": other.id, "leftover": False}]}, user.id
    )

    lo2 = _meal(db_session, user, D2)
    assert lo2.recipe_id == other.id
    assert lo2.leftover is False
    assert lo2.leftover_source_date is None
    assert lo2.leftover_source_meal is None


def test_repersisting_a_day_preserves_unchanged_leftover_link(db_session, user):
    """A leftover kept on re-persist re-resolves its source from the database."""
    bulk, _other = _bulk_plan(db_session, user)

    # Re-persist D2 alone, still a leftover of bulk; its source (D1) is not in
    # this payload and must be looked up from the existing plan.
    crud.set_meal_plan(
        db_session, {D2: [{"main_id": bulk.id, "leftover": True}]}, user.id
    )

    lo2 = _meal(db_session, user, D2)
    assert lo2.leftover is True
    assert lo2.leftover_source_date == date.fromisoformat(D1)
    assert lo2.leftover_source_meal == 1
