import json

import crud
from mealplanner.config import DEFAULT_PLAN_SETTINGS


def test_get_plan_settings_returns_defaults(db_session):
    settings = crud.get_plan_settings(db_session)
    assert settings == DEFAULT_PLAN_SETTINGS
    # A copy, not the shared default object.
    assert settings is not DEFAULT_PLAN_SETTINGS


def test_get_plan_settings_falls_back_to_defaults_without_overrides(db_session, user):
    assert crud.get_plan_settings(db_session, user.id) == DEFAULT_PLAN_SETTINGS


def test_plan_settings_endpoint_returns_defaults(auth_client):
    resp = auth_client.get("/plan/settings")
    assert resp.status_code == 200
    # JSON coerces the int meal-number keys to strings, so compare against
    # a JSON round-tripped copy of the defaults.
    assert resp.json() == json.loads(json.dumps(DEFAULT_PLAN_SETTINGS))


def test_plan_settings_endpoint_persists_overrides(auth_client):
    resp = auth_client.put("/plan/settings", json={"LEFTOVER_REPEAT_DEFAULT": 4})
    assert resp.status_code == 200
    assert resp.json()["LEFTOVER_REPEAT_DEFAULT"] == 4
    # The override survives a subsequent read.
    assert auth_client.get("/plan/settings").json()["LEFTOVER_REPEAT_DEFAULT"] == 4


def test_plan_settings_round_trips_tag_penalty_weight(auth_client):
    resp = auth_client.put("/plan/settings", json={"tag_penalty_weight": 2.0})
    assert resp.status_code == 200
    assert resp.json()["tag_penalty_weight"] == 2.0
    assert auth_client.get("/plan/settings").json()["tag_penalty_weight"] == 2.0


# --------------------------------------------------------------------------
# L4 cleanup: only settings something reads
# --------------------------------------------------------------------------
RETIRED_KEYS = {
    "MAX_LEFTOVERS_PER_WEEK", "LEFTOVER_ACCEPT_WEIGHT", "LEFTOVER_DAYPART_WEIGHT",
    "PROTECT_EXPLORE_SLOTS", "EXPLORE_PROTECTION_COST", "SOFT_HOLD_PENALTY",
}


def test_the_defaults_hold_only_settings_the_planner_reads():
    assert set(DEFAULT_PLAN_SETTINGS) == {
        "bulk_leftovers", "keep_days", "tag_penalty_weight",
        "LEFTOVER_REPEAT_DEFAULT", "LEFTOVER_REPEAT_BY_RECIPE", "LEFTOVER_SPACING_GAP",
        "MAX_LEFTOVERS_PER_DAY", "LEFTOVER_DAYPART_PREF", "MEAL_NUMBER_TO_DAYPART",
        "LEFTOVER_HOLD_MARGIN",
    }
    assert DEFAULT_PLAN_SETTINGS["LEFTOVER_HOLD_MARGIN"] == 15.0


def test_a_retired_setting_stored_earlier_does_not_come_back(db_session, user):
    user.plan_settings = {"SOFT_HOLD_PENALTY": 3.0, "LEFTOVER_SPACING_GAP": 1}
    db_session.flush()

    settings = crud.get_plan_settings(db_session, user.id)

    assert not RETIRED_KEYS & set(settings)
    assert settings["LEFTOVER_SPACING_GAP"] == 1


def test_the_generate_request_has_no_unused_fields():
    from schemas import MealPlanGenerate

    assert set(MealPlanGenerate.model_fields) == {
        "start", "end", "meals_per_day", "fridge", "epsilon", "avoid_tags", "reduce_tags",
        "seasonality_weight", "recency_weight", "tag_penalty_weight", "bulk_bonus_weight",
        "bulk_leftovers", "keep_days",
    }
