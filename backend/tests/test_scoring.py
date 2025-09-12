from datetime import date
import math
import pytest

from mealplanner.scoring import (
    score_recipe,
    tag_penalty,
    seasonality_bonus,
    recency_penalty,
    bulk_bonus,
)


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
