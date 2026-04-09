"""Verify that leftovers are properly spread through the plan after the fix."""
from datetime import date

from mealplanner.models import Recipe
from mealplanner.planner import generate_plan, Slot


def test_gap1_produces_leftovers(db_session):
    """GAP=1 with keep_days=3 should produce leftovers."""
    bulk = Recipe(title="Bulk", servings_default=1, score=5.0, bulk_prep=True, course="main")
    other = Recipe(title="Other", servings_default=1, score=4.0, bulk_prep=False, course="main")
    db_session.add_all([bulk, other])
    db_session.commit()

    slots = generate_plan(
        db_session,
        start=date(2024, 1, 1),
        days=7,
        meals_per_day=2,
        keep_days=3,
        epsilon=0.0,
        min_recipe_gap=0,
        plan_settings={"LEFTOVER_SPACING_GAP": 1},
        return_slots=True,
    )

    print("\n=== GAP=1, KEEP=3 ===")
    for s in slots:
        marker = " [LEFTOVER]" if s.leftover else ""
        hold = f" (hold={s.soft_hold_recipe_id})" if s.soft_hold_recipe_id else ""
        print(f"  {s.date} meal {s.meal_number}: {s.recipe.title}{marker}{hold}")

    leftover_count = sum(1 for s in slots if s.leftover)
    print(f"  Total leftovers: {leftover_count}")
    assert leftover_count > 0, "GAP=1 should produce leftovers"


def test_gap2_produces_leftovers(db_session):
    """GAP=2 with keep_days=7 should produce leftovers spread 2 days apart."""
    bulk = Recipe(title="Bulk", servings_default=1, score=5.0, bulk_prep=True, course="main")
    other = Recipe(title="Other", servings_default=1, score=4.0, bulk_prep=False, course="main")
    db_session.add_all([bulk, other])
    db_session.commit()

    slots = generate_plan(
        db_session,
        start=date(2024, 1, 1),
        days=7,
        meals_per_day=2,
        keep_days=7,
        epsilon=0.0,
        min_recipe_gap=0,
        plan_settings={"LEFTOVER_SPACING_GAP": 2},
        return_slots=True,
    )

    print("\n=== GAP=2, KEEP=7 ===")
    for s in slots:
        marker = " [LEFTOVER]" if s.leftover else ""
        hold = f" (hold={s.soft_hold_recipe_id})" if s.soft_hold_recipe_id else ""
        print(f"  {s.date} meal {s.meal_number}: {s.recipe.title}{marker}{hold}")

    leftover_count = sum(1 for s in slots if s.leftover)
    print(f"  Total leftovers: {leftover_count}")
    assert leftover_count > 0, "GAP=2 should produce leftovers"


def test_gap3_produces_leftovers(db_session):
    """GAP=3 with keep_days=7 should produce leftovers spread 3 days apart."""
    bulk = Recipe(title="Bulk", servings_default=1, score=5.0, bulk_prep=True, course="main")
    other = Recipe(title="Other", servings_default=1, score=4.0, bulk_prep=False, course="main")
    db_session.add_all([bulk, other])
    db_session.commit()

    slots = generate_plan(
        db_session,
        start=date(2024, 1, 1),
        days=7,
        meals_per_day=2,
        keep_days=7,
        epsilon=0.0,
        min_recipe_gap=0,
        plan_settings={"LEFTOVER_SPACING_GAP": 3},
        return_slots=True,
    )

    print("\n=== GAP=3, KEEP=7 ===")
    for s in slots:
        marker = " [LEFTOVER]" if s.leftover else ""
        hold = f" (hold={s.soft_hold_recipe_id})" if s.soft_hold_recipe_id else ""
        print(f"  {s.date} meal {s.meal_number}: {s.recipe.title}{marker}{hold}")

    leftover_count = sum(1 for s in slots if s.leftover)
    print(f"  Total leftovers: {leftover_count}")
    assert leftover_count > 0, "GAP=3 should produce leftovers"


def test_leftover_is_actually_spaced(db_session):
    """Verify that leftovers appear at least GAP days after cooking."""
    bulk = Recipe(title="Bulk", servings_default=1, score=5.0, bulk_prep=True, course="main")
    other = Recipe(title="Other", servings_default=1, score=4.0, bulk_prep=False, course="main")
    db_session.add_all([bulk, other])
    db_session.commit()

    gap = 2
    slots = generate_plan(
        db_session,
        start=date(2024, 1, 1),
        days=7,
        meals_per_day=2,
        keep_days=7,
        epsilon=0.0,
        min_recipe_gap=0,
        plan_settings={"LEFTOVER_SPACING_GAP": gap},
        return_slots=True,
    )

    # Find the first cook and the first leftover for Bulk
    first_cook = None
    first_leftover = None
    for s in slots:
        if s.recipe.title == "Bulk":
            if not s.leftover and first_cook is None:
                first_cook = s.date
            if s.leftover and first_leftover is None:
                first_leftover = s.date

    print(f"\n  First cook: {first_cook}")
    print(f"  First leftover: {first_leftover}")
    if first_cook and first_leftover:
        actual_gap = (first_leftover - first_cook).days
        print(f"  Actual gap: {actual_gap} days (expected >= {gap})")
        assert actual_gap >= gap, f"Leftover should be at least {gap} days after cooking"


def test_existing_test_still_passes(db_session):
    """Verify the existing test_leftover_ignores_recency_penalty still passes."""
    bulk = Recipe(
        title="Bulk", servings_default=1, score=5.0, bulk_prep=True, course="main"
    )
    other = Recipe(
        title="Other", servings_default=1, score=4.0, bulk_prep=False, course="main"
    )
    db_session.add_all([bulk, other])
    db_session.commit()

    plan = generate_plan(
        db_session,
        start=date(2024, 1, 1),
        days=3,
        meals_per_day=1,
        epsilon=0.0,
        min_recipe_gap=0,
    )
    assert plan == {
        "2024-01-01": ["Bulk"],
        "2024-01-02": ["Other"],
        "2024-01-03": ["Bulk (leftover)"],
    }
