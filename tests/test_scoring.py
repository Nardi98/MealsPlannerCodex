from datetime import date
import pytest

from mealplanner.scoring import score_recipe, tag_penalty


def test_all_in_season_old_recipe():
    today = date(2024, 6, 1)
    recipe = {
        "score": 1.0,
        "ingredients": [
            {"season_months": [6]},
            {"season_months": [5, 6]},
        ],
        "date_last_consumed": date(2024, 4, 1),
        "bulk_prep": False,
    }
    # base 1 + seasonality 1 + recency 0 + bulk 0 = 2
    assert score_recipe(recipe, today) == pytest.approx(2.0)


def test_recent_offseason_bulk_recipe():
    today = date(2024, 6, 1)
    recipe = {
        "score": 0.5,
        "ingredients": [
            {"season_months": [1]},
            {"season_months": []},
        ],
        "date_last_consumed": date(2024, 5, 30),
        "bulk_prep": True,
    }
    # base 0.5 + seasonality 0 + recency -1 + bulk 0.2 = -0.3
    assert score_recipe(recipe, today) == pytest.approx(-0.3)


def test_missing_data_defaults():
    today = date(2024, 1, 1)
    recipe = {"score": None}
    assert score_recipe(recipe, today) == pytest.approx(0.0)


def test_extreme_base_score():
    today = date(2024, 1, 1)
    recipe = {
        "score": 1_000_000,
        "date_last_consumed": date(2023, 12, 31),
        "ingredients": [],
    }
    # base 1e6 + recency -1 = 999999
    assert score_recipe(recipe, today) == pytest.approx(999_999.0)


def test_weight_parameters():
    today = date(2024, 6, 1)
    recipe = {
        "score": 1.0,
        "ingredients": [{"season_months": [6]}],
        "date_last_consumed": date(2024, 5, 30),
        "bulk_prep": True,
        "tags": ["spicy"],
    }
    # Only base score when weights are zero
    assert score_recipe(
        recipe,
        today,
        seasonality_weight=0,
        recency_weight=0,
        tag_penalty_weight=0,
        bulk_bonus_weight=0,
        reduce_tags={"spicy"},
    ) == pytest.approx(1.0)
    # Doubling all weights doubles magnitude of other components
    assert score_recipe(
        recipe,
        today,
        seasonality_weight=2,
        recency_weight=2,
        tag_penalty_weight=2,
        bulk_bonus_weight=2,
        reduce_tags={"spicy"},
    ) == pytest.approx(0.4)


def test_tag_penalty():
    recipe = {"tags": ["spicy", "vegan"]}
    assert tag_penalty(recipe, {"spicy"}) == pytest.approx(-0.5)
    assert tag_penalty(recipe, {"gluten-free"}) == pytest.approx(0.0)
