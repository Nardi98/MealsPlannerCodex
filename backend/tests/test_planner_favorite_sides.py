"""Automatic side assignment from a main's favorite sides.

A freshly cooked slot draws one favorite at random; the bulk leftovers that
follow reuse that same side, because the pair was cooked together once.
"""
import random
from datetime import date

from models import Recipe
from mealplanner.planner import generate_plan, pick_favorite_side


def _main(title, bulk=False, score=1.0):
    return Recipe(
        title=title,
        servings_default=1,
        score=score,
        bulk_prep=bulk,
        course="main",
    )


def _side(title):
    return Recipe(title=title, servings_default=1, score=1.0, course="side")


def test_pick_favorite_side_ignores_a_non_main_course(db_session):
    """Only mains take sides, even if legacy rows carry a pairing."""
    risotto = Recipe(
        title="Risotto", servings_default=1, score=1.0, course="first-course"
    )
    risotto.favorite_sides = [_side("Potatoes")]
    db_session.add(risotto)
    db_session.commit()

    assert pick_favorite_side(risotto, random.Random(0)) is None


def test_a_planned_first_course_gets_no_side(db_session):
    risotto = Recipe(
        title="Risotto", servings_default=1, score=1.0, course="first-course"
    )
    risotto.favorite_sides = [_side("Potatoes")]
    db_session.add(risotto)
    db_session.commit()

    slots = generate_plan(
        db_session,
        date(2024, 1, 1),
        days=1,
        meals_per_day=1,
        epsilon=0.0,
        min_recipe_gap=0,
        return_slots=True,
    )

    # A first course is still planned as a main slot candidate ...
    assert slots[0].recipe.title == "Risotto"
    # ... it just never gets an automatic side.
    assert slots[0].side_ids == []


def test_pick_favorite_side_returns_none_without_favorites(db_session):
    main = _main("Lonely Steak")
    db_session.add(main)
    db_session.commit()

    assert pick_favorite_side(main, random.Random(0)) is None


def test_pick_favorite_side_can_pick_any_favorite(db_session):
    """Uniform random: over many draws every favorite shows up."""
    main = _main("Roast")
    main.favorite_sides = [_side("Potatoes"), _side("Broccoli")]
    db_session.add(main)
    db_session.commit()

    rng = random.Random(0)
    seen = {pick_favorite_side(main, rng) for _ in range(50)}

    assert seen == {s.id for s in main.favorite_sides}


def test_generated_slot_gets_one_favorite_side(db_session):
    main = _main("Roast")
    potatoes = _side("Potatoes")
    main.favorite_sides = [potatoes]
    db_session.add(main)
    db_session.commit()

    slots = generate_plan(
        db_session,
        date(2024, 1, 1),
        days=1,
        meals_per_day=1,
        epsilon=0.0,
        min_recipe_gap=0,
        return_slots=True,
    )

    assert [s.side_ids for s in slots] == [[potatoes.id]]


def test_main_without_favorites_gets_no_side(db_session):
    db_session.add(_main("Plain Steak"))
    db_session.commit()

    slots = generate_plan(
        db_session,
        date(2024, 1, 1),
        days=1,
        meals_per_day=1,
        epsilon=0.0,
        min_recipe_gap=0,
        return_slots=True,
    )

    assert [s.side_ids for s in slots] == [[]]


def test_leftovers_repeat_the_side_cooked_with_the_source(db_session):
    """The agreed rule: cook the pair once, the leftovers carry it along."""
    main = _main("Bulk", bulk=True)
    main.favorite_sides = [_side("Potatoes"), _side("Broccoli"), _side("Salad")]
    db_session.add(main)
    db_session.commit()

    slots = generate_plan(
        db_session,
        date(2024, 1, 1),
        days=4,
        meals_per_day=1,
        epsilon=0.0,
        keep_days=2,
        min_recipe_gap=0,
        plan_settings={"LEFTOVER_SPACING_GAP": 1},
        return_slots=True,
        rng=random.Random(0),
    )

    # Days 1+2 are one cooked batch, days 3+4 the next (see
    # test_generate_plan_leftover_expiry: leftover flags are F, T, F, T).
    assert [s.leftover for s in slots] == [False, True, False, True]
    assert slots[1].side_ids == slots[0].side_ids
    assert slots[3].side_ids == slots[2].side_ids
    assert len(slots[0].side_ids) == 1


def test_a_main_cooked_fresh_again_rerolls_its_side(db_session):
    """Two independent cooking events must be free to draw different sides."""
    main = _main("Bulk", bulk=True)
    main.favorite_sides = [_side("Potatoes"), _side("Broccoli"), _side("Salad")]
    db_session.add(main)
    db_session.commit()

    def batch_sides(seed):
        slots = generate_plan(
            db_session,
            date(2024, 1, 1),
            days=4,
            meals_per_day=1,
            epsilon=0.0,
            keep_days=2,
            min_recipe_gap=0,
            plan_settings={"LEFTOVER_SPACING_GAP": 1},
            return_slots=True,
            rng=random.Random(seed),
        )
        return slots[0].side_ids, slots[2].side_ids

    # Across seeds the two cooked slots must not be locked to each other.
    assert any(first != second for first, second in map(batch_sides, range(20)))
