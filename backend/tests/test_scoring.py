from datetime import date
import math
import pytest

from mealplanner.scoring import (
    score_recipe,
    tag_penalty,
    seasonality_bonus,
    recency_penalty,
    bulk_bonus,
    SEASONALITY_BONUS_SCALE,
)


def test_recency_penalty_decays_monotonically():
    """More days since last planned means a smaller-magnitude penalty."""
    planned = date(2024, 6, 15)
    near = {"date_last_planned": date(2024, 6, 13)}   # 2 days
    far = {"date_last_planned": date(2024, 6, 9)}     # 6 days
    near_pen = recency_penalty(near, planned)
    far_pen = recency_penalty(far, planned)
    assert near_pen < far_pen <= 0
    assert abs(near_pen) > abs(far_pen)


def test_recency_penalty_no_penalty_for_future_last_planned():
    """A recipe last planned after the planning date is not yet consumed."""
    planned = date(2024, 6, 1)
    recipe = {"date_last_planned": date(2024, 6, 10)}
    assert recency_penalty(recipe, planned) == 0.0


def test_recency_penalty_zero_outside_window():
    planned = date(2024, 6, 30)
    recipe = {"date_last_planned": date(2024, 6, 1)}  # 29 days > window
    assert recency_penalty(recipe, planned) == 0.0


def test_seasonality_bonus_in_season_is_positive():
    today = date(2024, 6, 1)
    recipe = {"ingredients": [{"season_months": [6]}, {"season_months": [5, 6]}]}
    assert seasonality_bonus(recipe, today) == pytest.approx(SEASONALITY_BONUS_SCALE)


def test_seasonality_bonus_out_of_season_is_symmetric_negative():
    today = date(2024, 6, 1)
    recipe = {"ingredients": [{"season_months": [1]}, {"season_months": [12]}]}
    assert seasonality_bonus(recipe, today) == pytest.approx(-SEASONALITY_BONUS_SCALE)


def test_seasonality_bonus_missing_data_is_neutral():
    today = date(2024, 6, 1)
    recipe = {"ingredients": [{"season_months": []}, {"season_months": list(range(1, 13))}]}
    assert seasonality_bonus(recipe, today) == pytest.approx(0.0)


def test_all_in_season_old_recipe():
    today = date(2024, 6, 1)
    recipe = {
        "score": 1.0,
        "ingredients": [
            {"season_months": [6]},
            {"season_months": [5, 6]},
        ],
        "date_last_planned": date(2024, 4, 1),
        "bulk_prep": False,
    }
    expected = 3 * math.tanh(1.0) + seasonality_bonus(recipe, today)
    assert score_recipe(recipe, today) == pytest.approx(expected)


def test_recent_offseason_bulk_recipe():
    today = date(2024, 6, 1)
    recipe = {
        "score": 0.5,
        "ingredients": [
            {"season_months": [1]},
            {"season_months": []},
        ],
        "date_last_planned": date(2024, 5, 30),
        "bulk_prep": True,
    }
    expected = (
        3 * math.tanh(0.5)
        + seasonality_bonus(recipe, today)
        + recency_penalty(recipe, today)
        + bulk_bonus(recipe)
    )
    assert score_recipe(recipe, today) == pytest.approx(expected)


def test_missing_data_defaults():
    today = date(2024, 1, 1)
    recipe = {
        "score": None,
        "date_last_planned": date(2023, 1, 1),
        "ingredients": [],
    }
    assert score_recipe(recipe, today) == pytest.approx(0.0)


def test_extreme_base_score():
    today = date(2024, 1, 1)
    recipe = {
        "score": 1_000_000,
        "date_last_planned": date(2023, 12, 31),
        "ingredients": [],
    }
    expected = 3 * math.tanh(1_000_000) + recency_penalty(recipe, today)
    assert score_recipe(recipe, today) == pytest.approx(expected)


def test_weight_parameters():
    today = date(2024, 6, 1)
    recipe = {
        "score": 1.0,
        "ingredients": [{"season_months": [6]}],
        "date_last_planned": date(2024, 5, 30),
        "bulk_prep": True,
        "tags": ["spicy"],
    }
    # Only bounded base score when weights are zero
    assert score_recipe(
        recipe,
        today,
        seasonality_weight=0,
        recency_weight=0,
        tag_penalty_weight=0,
        bulk_bonus_weight=0,
        reduce_tags={"spicy"},
    ) == pytest.approx(3 * math.tanh(1.0))
    # Doubling all weights doubles magnitude of other components
    assert score_recipe(
        recipe,
        today,
        seasonality_weight=2,
        recency_weight=2,
        tag_penalty_weight=2,
        bulk_bonus_weight=2,
        reduce_tags={"spicy"},
    ) == pytest.approx(
        3 * math.tanh(1.0)
        + 2 * seasonality_bonus(recipe, today)
        + 2 * recency_penalty(recipe, today)
        + 2 * bulk_bonus(recipe)
        + 2 * tag_penalty(recipe, {"spicy"})
    )


def test_tag_penalty():
    recipe = {"tags": ["spicy", "vegan"]}
    assert tag_penalty(recipe, {"spicy"}) == pytest.approx(-3.0)
    assert tag_penalty(recipe, {"gluten-free"}) == pytest.approx(0.0)
