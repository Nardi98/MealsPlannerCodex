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
D5 = "2024-01-05"
D6 = "2024-01-06"


def _meal(session, user, day, number=1):
    return session.get(Meal, (user.id, date.fromisoformat(day), number))


def _recipe_at(session, user, day, number=1):
    """Recipe id currently sitting in a slot (None when empty)."""
    meal = _meal(session, user, day, number)
    return meal.recipe_id if meal else None


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


# --- Multiple / sequential swaps -------------------------------------------
#
# A single swap can look correct by luck; these chain several swaps and assert
# the whole plan is exactly the expected permutation after each step, so a swap
# that corrupts unrelated slots is caught.


def test_sequential_swaps_are_each_one_to_one(db_session, user, make_recipe):
    a = make_recipe("A")
    b = make_recipe("B")
    c = make_recipe("C")
    d = make_recipe("D")
    crud.set_meal_plan(
        db_session,
        {
            D1: [{"main_id": a.id}],
            D2: [{"main_id": b.id}],
            D3: [{"main_id": c.id}],
            D4: [{"main_id": d.id}],
        },
        user.id,
    )

    def state():
        return {d_: _recipe_at(db_session, user, d_) for d_ in (D1, D2, D3, D4)}

    assert state() == {D1: a.id, D2: b.id, D3: c.id, D4: d.id}

    crud.swap_meals(db_session, (D1, 1), (D3, 1), user.id)
    assert state() == {D1: c.id, D2: b.id, D3: a.id, D4: d.id}

    crud.swap_meals(db_session, (D2, 1), (D4, 1), user.id)
    assert state() == {D1: c.id, D2: d.id, D3: a.id, D4: b.id}

    crud.swap_meals(db_session, (D1, 1), (D2, 1), user.id)
    assert state() == {D1: d.id, D2: c.id, D3: a.id, D4: b.id}

    # Adjacent chained swaps must not disturb untouched slots (D4 stays b).
    crud.swap_meals(db_session, (D2, 1), (D3, 1), user.id)
    assert state() == {D1: d.id, D2: a.id, D3: c.id, D4: b.id}


def test_swap_and_swap_back_restores_original(db_session, user, make_recipe):
    a = make_recipe("A")
    b = make_recipe("B")
    sa = make_recipe("SideA", course="side")
    crud.set_meal_plan(
        db_session,
        {
            D1: [{"main_id": a.id, "side_ids": [sa.id]}],
            D2: [{"main_id": b.id}],
        },
        user.id,
    )

    crud.swap_meals(db_session, (D1, 1), (D2, 1), user.id)
    crud.swap_meals(db_session, (D1, 1), (D2, 1), user.id)

    m1 = _meal(db_session, user, D1)
    m2 = _meal(db_session, user, D2)
    assert m1.recipe_id == a.id
    assert m2.recipe_id == b.id
    assert [s.side_recipe_id for s in m1.sides] == [sa.id]
    assert [s.side_recipe_id for s in m2.sides] == []


def test_same_day_cross_slot_swap(db_session, user, make_recipe):
    a = make_recipe("A")
    b = make_recipe("B")
    # Two meals on the same day (lunch/dinner).
    crud.set_meal_plan(
        db_session,
        {D1: [{"main_id": a.id}, {"main_id": b.id}]},
        user.id,
    )

    crud.swap_meals(db_session, (D1, 1), (D1, 2), user.id)

    assert _recipe_at(db_session, user, D1, 1) == b.id
    assert _recipe_at(db_session, user, D1, 2) == a.id


def test_self_swap_is_noop(db_session, user, make_recipe):
    a = make_recipe("A")
    sa = make_recipe("SideA", course="side")
    crud.set_meal_plan(
        db_session,
        {D1: [{"main_id": a.id, "side_ids": [sa.id]}]},
        user.id,
    )

    result = crud.swap_meals(db_session, (D1, 1), (D1, 1), user.id)
    assert result is not None

    m1 = _meal(db_session, user, D1)
    assert m1.recipe_id == a.id
    assert [s.side_recipe_id for s in m1.sides] == [sa.id]


# --- Accepted flag ----------------------------------------------------------


def test_swap_two_accepted_meals_keeps_both_accepted(db_session, user, make_recipe):
    a = make_recipe("A")
    b = make_recipe("B")
    crud.set_meal_plan(
        db_session,
        {D1: [{"main_id": a.id}], D2: [{"main_id": b.id}]},
        user.id,
    )
    crud.mark_meal_accepted(db_session, date.fromisoformat(D1), 1, True, user.id)
    crud.mark_meal_accepted(db_session, date.fromisoformat(D2), 1, True, user.id)

    crud.swap_meals(db_session, (D1, 1), (D2, 1), user.id)

    m1 = _meal(db_session, user, D1)
    m2 = _meal(db_session, user, D2)
    assert m1.accepted is True and m2.accepted is True
    assert m1.recipe_id == b.id and m2.recipe_id == a.id


def test_swap_accepted_flag_stays_with_position_both_directions(
    db_session, user, make_recipe
):
    a = make_recipe("A")
    b = make_recipe("B")
    crud.set_meal_plan(
        db_session,
        {D1: [{"main_id": a.id}], D2: [{"main_id": b.id}]},
        user.id,
    )
    # Only D2 accepted.
    crud.mark_meal_accepted(db_session, date.fromisoformat(D2), 1, True, user.id)

    crud.swap_meals(db_session, (D1, 1), (D2, 1), user.id)
    assert _meal(db_session, user, D1).accepted is False
    assert _meal(db_session, user, D2).accepted is True

    # Swap back: acceptance still tracks the position, not the recipe.
    crud.swap_meals(db_session, (D1, 1), (D2, 1), user.id)
    assert _meal(db_session, user, D1).accepted is False
    assert _meal(db_session, user, D2).accepted is True


# --- Leftover edge cases ----------------------------------------------------


def test_swap_two_leftovers_of_same_recipe(db_session, user, make_recipe):
    bulk = make_recipe("Bulk", bulk_prep=True)
    other1 = make_recipe("Other1")
    other2 = make_recipe("Other2")
    # Source D1, leftovers D2 and D3 of the same bulk recipe.
    crud.set_meal_plan(
        db_session,
        {
            D1: [{"main_id": bulk.id, "leftover": False}],
            D2: [{"main_id": bulk.id, "leftover": True}],
            D3: [{"main_id": bulk.id, "leftover": True}],
            D4: [{"main_id": other1.id}],
            D5: [{"main_id": other2.id}],
        },
        user.id,
    )

    # Swap the two leftovers against each other's neighbours doesn't apply;
    # instead move each leftover onto an unrelated fresh slot and back.
    crud.swap_meals(db_session, (D2, 1), (D4, 1), user.id)
    crud.swap_meals(db_session, (D3, 1), (D5, 1), user.id)

    # Bulk now sits on D1 (source), D4 and D5 (leftovers); D2/D3 hold the others.
    assert _meal(db_session, user, D1).leftover is False
    assert _recipe_at(db_session, user, D2) == other1.id
    assert _recipe_at(db_session, user, D3) == other2.id
    d4 = _meal(db_session, user, D4)
    d5 = _meal(db_session, user, D5)
    assert d4.recipe_id == bulk.id and d4.leftover is True
    assert d5.recipe_id == bulk.id and d5.leftover is True
    assert d4.leftover_source_date == date.fromisoformat(D1)
    assert d5.leftover_source_date == date.fromisoformat(D1)


def test_swap_does_not_convert_unrelated_fresh_occurrence(
    db_session, user, make_recipe
):
    """A separately-planned fresh occurrence stays fresh after an unrelated swap.

    Bulk on D1(source)+D2(leftover) is one batch. A distinct fresh Bulk on D5
    (its own meal, no leftover) must not be dragged into the batch when a swap
    elsewhere triggers a leftover recompute for the recipe.
    """
    bulk = make_recipe("Bulk", bulk_prep=True)
    x = make_recipe("X")
    crud.set_meal_plan(
        db_session,
        {
            D1: [{"main_id": bulk.id, "leftover": False}],
            D2: [{"main_id": bulk.id, "leftover": True}],
            D3: [{"main_id": x.id}],
            D5: [{"main_id": bulk.id, "leftover": False}],
        },
        user.id,
    )
    assert _meal(db_session, user, D5).leftover is False

    # Swap the unrelated X (D3) with the D2 leftover; recompute runs for bulk.
    crud.swap_meals(db_session, (D2, 1), (D3, 1), user.id)

    # The independent fresh D5 bulk must remain fresh.
    assert _meal(db_session, user, D5).leftover is False


def test_swap_preserves_two_separate_batches(db_session, user, make_recipe):
    """Two independent cook-batches of one recipe are not merged by a swap.

    The planner can schedule the same bulk recipe as two separate batches (e.g.
    cooked fresh in different weeks). A swap touching one meal must not collapse
    both batches into a single leftover chain -- each batch keeps its own fresh
    source.
    """
    bulk = make_recipe("Bulk", bulk_prep=True)
    x = make_recipe("X")
    crud.set_meal_plan(
        db_session,
        {
            D1: [{"main_id": bulk.id, "leftover": False}],  # batch 1 source
            D2: [{"main_id": bulk.id, "leftover": True}],   # batch 1 leftover
            D3: [{"main_id": x.id}],
            D4: [{"main_id": bulk.id, "leftover": False}],  # batch 2 source
            D5: [{"main_id": bulk.id, "leftover": True}],   # batch 2 leftover
        },
        user.id,
    )

    # Swap the unrelated X (D3) with batch-1's leftover (D2) -> recompute bulk.
    crud.swap_meals(db_session, (D2, 1), (D3, 1), user.id)

    # Batch 2's source (D4) must stay a fresh source, not become a leftover.
    d4 = _meal(db_session, user, D4)
    d5 = _meal(db_session, user, D5)
    assert d4.recipe_id == bulk.id and d4.leftover is False
    assert d5.recipe_id == bulk.id and d5.leftover is True
    # D5 belongs to batch 2, so it links to D4, not the earlier D1.
    assert d5.leftover_source_date == date.fromisoformat(D4)


def test_swap_leftover_whose_source_is_a_third_meal(db_session, user, make_recipe):
    bulk = make_recipe("Bulk", bulk_prep=True)
    other = make_recipe("Other")
    # Source D1, leftover D3 (source is the third meal D1, not the swap peers).
    crud.set_meal_plan(
        db_session,
        {
            D1: [{"main_id": bulk.id, "leftover": False}],
            D3: [{"main_id": bulk.id, "leftover": True}],
            D5: [{"main_id": other.id}],
        },
        user.id,
    )

    # Move the leftover (D3) onto D5; source stays on D1.
    crud.swap_meals(db_session, (D3, 1), (D5, 1), user.id)

    assert _meal(db_session, user, D1).leftover is False
    assert _recipe_at(db_session, user, D3) == other.id
    d5 = _meal(db_session, user, D5)
    assert d5.recipe_id == bulk.id and d5.leftover is True
    assert d5.leftover_source_date == date.fromisoformat(D1)


def test_swap_source_out_of_three_occurrence_group(db_session, user, make_recipe):
    """Source + two leftovers: exactly one source survives, links stay chronological."""
    bulk = make_recipe("Bulk", bulk_prep=True)
    other = make_recipe("Other")
    crud.set_meal_plan(
        db_session,
        {
            D1: [{"main_id": bulk.id, "leftover": False}],
            D2: [{"main_id": bulk.id, "leftover": True}],
            D3: [{"main_id": bulk.id, "leftover": True}],
            D5: [{"main_id": other.id}],
        },
        user.id,
    )

    # Move the source (D1) out to D5; the earliest remaining bulk becomes source.
    crud.swap_meals(db_session, (D1, 1), (D5, 1), user.id)

    bulk_meals = [
        _meal(db_session, user, d_)
        for d_ in (D1, D2, D3, D5)
        if _recipe_at(db_session, user, d_) == bulk.id
    ]
    sources = [m for m in bulk_meals if not m.leftover]
    # Exactly one freshly-prepared source among the group.
    assert len(sources) == 1
    source = sources[0]
    # It is the earliest bulk occurrence.
    assert source.plan_date == min(m.plan_date for m in bulk_meals)
    # Every leftover points at that source.
    for m in bulk_meals:
        if m.leftover:
            assert m.leftover_source_date == source.plan_date
            assert m.leftover_source_meal == source.meal_number


# --- Sides on both slots ----------------------------------------------------


def test_swap_exchanges_multiple_sides_both_directions(db_session, user, make_recipe):
    a = make_recipe("A")
    b = make_recipe("B")
    sa1 = make_recipe("SideA1", course="side")
    sa2 = make_recipe("SideA2", course="side")
    sb1 = make_recipe("SideB1", course="side")
    crud.set_meal_plan(
        db_session,
        {
            D1: [{"main_id": a.id, "side_ids": [sa1.id, sa2.id]}],
            D2: [{"main_id": b.id, "side_ids": [sb1.id]}],
        },
        user.id,
    )

    crud.swap_meals(db_session, (D1, 1), (D2, 1), user.id)

    m1 = _meal(db_session, user, D1)
    m2 = _meal(db_session, user, D2)
    # Full one-to-one exchange with contiguous 1..n positions and no stale rows.
    assert [(s.position, s.side_recipe_id) for s in m1.sides] == [(1, sb1.id)]
    assert [(s.position, s.side_recipe_id) for s in m2.sides] == [
        (1, sa1.id),
        (2, sa2.id),
    ]
