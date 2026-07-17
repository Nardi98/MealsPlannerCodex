"""Deleting a recipe that a plan already references must not fail.

Reported from a real run: deleting a side dish raised ForeignKeyViolation on
``meal_side_dishes_side_recipe_id_fkey``. Deleting a recipe is a user-facing
action and must silently take the recipe out of any plan it appears in.
"""
from datetime import date

import crud
import models


PLAN_DATE = date(2026, 7, 20)


def _plan_with(db_session, user, main, side_ids):
    crud.set_meal_plan(
        db_session,
        {PLAN_DATE.isoformat(): [{"main_id": main.id, "side_ids": side_ids}]},
        user.id,
    )


def _meal(db_session, user):
    return db_session.get(models.Meal, (user.id, PLAN_DATE, 1))


def test_deleting_a_planned_side_dish_removes_it_from_the_meal(
    db_session, user, make_recipe
):
    main = make_recipe("Roast Chicken")
    potatoes = make_recipe("Mashed Potatoes", "side")
    broccoli = make_recipe("Steamed Broccoli", "side")
    db_session.flush()
    _plan_with(db_session, user, main, [potatoes.id, broccoli.id])

    db_session.delete(potatoes)
    db_session.flush()

    assert [s.side_recipe.title for s in _meal(db_session, user).sides] == [
        "Steamed Broccoli"
    ]


def test_a_side_can_be_added_again_after_one_was_deleted(
    db_session, user, make_recipe
):
    """``position`` is part of the PK, so the cascade must not leave a gap."""
    main = make_recipe("Roast Chicken")
    potatoes = make_recipe("Mashed Potatoes", "side")
    broccoli = make_recipe("Steamed Broccoli", "side")
    coleslaw = make_recipe("Coleslaw", "side")
    db_session.flush()
    # Potatoes sit at position 1, broccoli at 2.
    _plan_with(db_session, user, main, [potatoes.id, broccoli.id])

    db_session.delete(potatoes)
    db_session.flush()
    db_session.expire_all()

    crud.add_meal_side(db_session, PLAN_DATE, 1, coleslaw.id, user.id)

    titles = [s.side_recipe.title for s in _meal(db_session, user).sides]
    assert titles == ["Steamed Broccoli", "Coleslaw"]


def test_deleting_a_side_that_is_also_a_favorite_keeps_the_main(
    db_session, user, make_recipe
):
    """The reported case: a side used in a plan *and* pinned as a favorite."""
    main = make_recipe("Roast Chicken")
    potatoes = make_recipe("Mashed Potatoes", "side")
    main.favorite_sides = [potatoes]
    db_session.flush()
    _plan_with(db_session, user, main, [potatoes.id])

    db_session.delete(potatoes)
    db_session.flush()
    db_session.expire_all()

    reloaded = db_session.get(models.Recipe, main.id)
    assert reloaded.favorite_sides == []
    assert _meal(db_session, user).sides == []


def test_deleting_a_planned_main_dish_empties_its_slot(
    db_session, user, make_recipe
):
    """Same defect class as the side above: Meal.recipe_id has no ondelete.

    ``crud.get_plan`` already skips meals whose recipe is gone, so emptying the
    slot is the behaviour the read path expects.
    """
    main = make_recipe("Roast Chicken")
    db_session.flush()
    _plan_with(db_session, user, main, [])

    db_session.delete(main)
    db_session.flush()

    assert crud.get_plan(db_session, PLAN_DATE, user_id=user.id) == {
        PLAN_DATE.isoformat(): []
    }
