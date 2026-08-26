"""A day whose lunch recipe was deleted must still serve over the API.

Reported from a real run: deleting a recipe the current plan used made every
subsequent ``GET /meal-plans`` return 500 ("failed to fetch" in the UI) with
``ResponseValidationError ... input: None``. ``crud._plan_day_slots`` serves a
day as an array indexed by ``meal_number``, so a missing lunch is a ``None``
hole at index 0 -- which the route's ``List[MealOut]`` response model rejected.
"""
from datetime import date

import crud


PLAN_DATE = date(2026, 8, 26)


def test_day_missing_its_lunch_serves_a_null_slot(
    db_session, user, make_recipe, auth_client
):
    lunch = make_recipe("Deleted Lunch")
    dinner = make_recipe("Surviving Dinner")
    db_session.flush()
    crud.set_meal_plan(
        db_session,
        {PLAN_DATE.isoformat(): [{"main_id": lunch.id}, {"main_id": dinner.id}]},
        user.id,
    )

    db_session.delete(lunch)
    db_session.flush()
    db_session.expire_all()

    resp = auth_client.get("/meal-plans", params={"plan_date": PLAN_DATE.isoformat()})

    assert resp.status_code == 200
    day = resp.json()[PLAN_DATE.isoformat()]
    assert day[0] is None
    assert day[1]["recipe"] == "Surviving Dinner"
    assert day[1]["meal_number"] == 2


def test_assignment_can_name_its_own_meal_number(
    db_session, user, make_recipe, auth_client
):
    """Saving a gapped day must not promote dinner into the lunch slot.

    ``save_plan`` numbers meals by their position in the list, so a client that
    drops an empty lunch before posting would silently move dinner to slot 1.
    An explicit ``meal_number`` pins the slot.
    """
    dinner = make_recipe("Dinner Only")
    db_session.flush()

    resp = auth_client.post(
        "/meal-plans",
        json={
            "plan_date": PLAN_DATE.isoformat(),
            "plan": {
                PLAN_DATE.isoformat(): [
                    {"main_id": dinner.id, "side_ids": [], "meal_number": 2}
                ]
            },
        },
    )

    assert resp.status_code == 200
    day = resp.json()[PLAN_DATE.isoformat()]
    assert day[0] is None
    assert day[1]["recipe"] == "Dinner Only"
    assert day[1]["meal_number"] == 2


def test_out_of_range_meal_number_is_rejected(
    db_session, user, make_recipe, auth_client
):
    """A slot outside Lunch/Dinner must fail at the boundary, not on the CHECK.

    ``meals_meal_number_check`` would otherwise turn a bad request into a 500.
    """
    dinner = make_recipe("Dinner Only")
    db_session.flush()

    resp = auth_client.post(
        "/meal-plans",
        json={
            "plan_date": PLAN_DATE.isoformat(),
            "plan": {
                PLAN_DATE.isoformat(): [
                    {"main_id": dinner.id, "side_ids": [], "meal_number": 3}
                ]
            },
        },
    )

    assert resp.status_code == 422
