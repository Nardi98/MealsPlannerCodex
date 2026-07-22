"""Swapping two meals' positions exchanges recipe + sides and keeps leftovers
chronologically consistent.

``crud.swap_meals`` exchanges the recipe and ordered side dishes between two
filled slots, leaving each slot's ``accepted`` flag in place. Afterwards leftover
state is re-derived so a recipe's earliest occurrence is the freshly-prepared
source and every later occurrence is a leftover -- moving a leftover before its
source (or the source after a leftover) flips which one is prepared.
"""

from datetime import date

import pytest

import crud
from models import Meal


D1 = "2024-01-01"
D2 = "2024-01-02"
D3 = "2024-01-03"
D4 = "2024-01-04"


def _meal(session, user, day, number=1):
    return session.get(Meal, (user.id, date.fromisoformat(day), number))


def test_swap_exchanges_recipe_and_sides(db_session, user, make_recipe):
    a = make_recipe("A")
    b = make_recipe("B")
    sa = make_recipe("SideA", course="side")
    sb = make_recipe("SideB", course="side")
    crud.set_meal_plan(
        db_session,
        {
            D1: [{"main_id": a.id, "side_ids": [sa.id]}],
            D2: [{"main_id": b.id, "side_ids": [sb.id]}],
        },
        user.id,
    )

    result = crud.swap_meals(db_session, (D1, 1), (D2, 1), user.id)
    assert result is not None

    m1 = _meal(db_session, user, D1)
    m2 = _meal(db_session, user, D2)
    assert m1.recipe_id == b.id
    assert m2.recipe_id == a.id
    assert [s.side_recipe_id for s in m1.sides] == [sb.id]
    assert [s.side_recipe_id for s in m2.sides] == [sa.id]


def test_swap_keeps_accepted_with_position(db_session, user, make_recipe):
    a = make_recipe("A")
    b = make_recipe("B")
    crud.set_meal_plan(
        db_session,
        {D1: [{"main_id": a.id}], D2: [{"main_id": b.id}]},
        user.id,
    )
    crud.mark_meal_accepted(db_session, date.fromisoformat(D1), 1, True, user.id)

    crud.swap_meals(db_session, (D1, 1), (D2, 1), user.id)

    m1 = _meal(db_session, user, D1)
    m2 = _meal(db_session, user, D2)
    # accepted stays with the position, not the recipe.
    assert m1.accepted is True
    assert m2.accepted is False
    assert m1.recipe_id == b.id


def test_swap_leftover_stays_after_source(db_session, user, make_recipe):
    bulk = make_recipe("Bulk", bulk_prep=True)
    other = make_recipe("Other")
    crud.set_meal_plan(
        db_session,
        {
            D1: [{"main_id": bulk.id, "leftover": False}],
            D2: [{"main_id": bulk.id, "leftover": True}],
            D3: [{"main_id": other.id}],
        },
        user.id,
    )

    # Move the leftover (D2) to D3; it is still after the D1 source.
    crud.swap_meals(db_session, (D2, 1), (D3, 1), user.id)

    src = _meal(db_session, user, D1)
    other_slot = _meal(db_session, user, D2)
    lo = _meal(db_session, user, D3)
    assert src.leftover is False
    assert other_slot.recipe_id == other.id and other_slot.leftover is False
    assert lo.recipe_id == bulk.id and lo.leftover is True
    assert lo.leftover_source_date == date.fromisoformat(D1)


def test_swap_source_after_leftover_inverts(db_session, user, make_recipe):
    """Moving the source to after a leftover makes the earliest one prepared."""
    bulk = make_recipe("Bulk", bulk_prep=True)
    other = make_recipe("Other")
    crud.set_meal_plan(
        db_session,
        {
            D1: [{"main_id": bulk.id, "leftover": False}],
            D3: [{"main_id": bulk.id, "leftover": True}],
            D4: [{"main_id": other.id}],
        },
        user.id,
    )

    # Swap the D1 source with the D4 other-recipe: bulk source now sits on D4,
    # after the D3 leftover. The earliest bulk (D3) must become the source.
    crud.swap_meals(db_session, (D1, 1), (D4, 1), user.id)

    d1 = _meal(db_session, user, D1)
    d3 = _meal(db_session, user, D3)
    d4 = _meal(db_session, user, D4)
    assert d1.recipe_id == other.id and d1.leftover is False
    assert d3.recipe_id == bulk.id and d3.leftover is False  # now the source
    assert d4.recipe_id == bulk.id and d4.leftover is True    # now the leftover
    assert d4.leftover_source_date == date.fromisoformat(D3)


def test_swap_missing_slot_returns_none(db_session, user, make_recipe):
    a = make_recipe("A")
    crud.set_meal_plan(db_session, {D1: [{"main_id": a.id}]}, user.id)

    # D2 has no meal -> cannot swap.
    assert crud.swap_meals(db_session, (D1, 1), (D2, 1), user.id) is None
