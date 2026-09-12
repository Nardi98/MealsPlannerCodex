from datetime import date, timedelta
import math
import pytest

from mealplanner.scoring import (
    score_recipe,
    tag_penalty,
    seasonality_bonus,
    recency_penalty,
    bulk_bonus,
    ingredient_repetition_penalty,
    tag_repetition_penalty,
    SEASONALITY_BONUS_SCALE,
    BULK_PREP_BONUS,
    DEFAULT_TAG_PENALTY,
    BASE_SQUASH_SCALE,
    BASE_SQUASH_SHARPNESS,
    INGREDIENT_REPEAT_MAX_PENALTY,
    INGREDIENT_REPEAT_HALF_LIFE_DAYS,
    INGREDIENT_REPEAT_WINDOW_DAYS,
    TAG_REPEAT_MAX_PENALTY,
    TAG_REPEAT_HALF_LIFE_DAYS,
    exploration_weight,
    fridge_bonus,
    FRIDGE_BONUS_SCALE,
    EXPLORE_COOLDOWN_DAYS,
    EXPLORE_NEW_RECIPE_STALENESS_DAYS,
    EXPLORE_DAMP_SCALE,
)


SLOT = date(2024, 6, 30)


def squashed_base(norm):
    """The base-score term for a normalised score, re-derived from the constants.

    Deliberately spelled out rather than imported from ``scoring`` so the
    assertions stay independent of the production formula.
    """

    return BASE_SQUASH_SCALE * math.tanh(BASE_SQUASH_SHARPNESS * norm)


def test_exploration_weight_grows_linearly_with_staleness():
    """Twice as stale means twice the weight (relative pick-probability)."""
    one_month = exploration_weight(
        slot_date=SLOT,
        date_last_rejected=SLOT - timedelta(days=30),
        last_proposed=None,
        score=0.0,
    )
    two_months = exploration_weight(
        slot_date=SLOT,
        date_last_rejected=SLOT - timedelta(days=60),
        last_proposed=None,
        score=0.0,
    )
    assert two_months == pytest.approx(2 * one_month)


def test_exploration_weight_zero_within_cooldown():
    """A recipe proposed within the cooldown is out of the explore pool."""
    w = exploration_weight(
        slot_date=SLOT,
        date_last_rejected=SLOT - timedelta(days=90),
        last_proposed=SLOT - timedelta(days=int(EXPLORE_COOLDOWN_DAYS) - 1),
        score=0.0,
    )
    assert w == 0.0


def test_exploration_weight_null_anchor_is_maximally_stale():
    """Never-rejected recipes audition strongly (treated as far-past anchor)."""
    new = exploration_weight(
        slot_date=SLOT, date_last_rejected=None, last_proposed=None, score=0.0
    )
    month_old = exploration_weight(
        slot_date=SLOT,
        date_last_rejected=SLOT - timedelta(days=30),
        last_proposed=None,
        score=0.0,
    )
    assert new == pytest.approx(EXPLORE_NEW_RECIPE_STALENESS_DAYS)
    assert new > month_old


def test_exploration_weight_negative_score_damps_monotonically():
    """More negative scores shrink the weight; losers fade, near-misses don't."""
    kwargs = dict(
        slot_date=SLOT,
        date_last_rejected=SLOT - timedelta(days=60),
        last_proposed=None,
    )
    mild = exploration_weight(score=-10.0, **kwargs)
    harsh = exploration_weight(score=-80.0, **kwargs)
    neutral = exploration_weight(score=0.0, **kwargs)
    assert 0 < harsh < mild < neutral


def test_exploration_weight_nonnegative_score_not_damped():
    """Positive scores get no damping (factor 1)."""
    kwargs = dict(
        slot_date=SLOT,
        date_last_rejected=SLOT - timedelta(days=60),
        last_proposed=None,
    )
    assert exploration_weight(score=0.0, **kwargs) == pytest.approx(
        exploration_weight(score=50.0, **kwargs)
    )
    # Sanity: damp scale is the halving constant for negative scores.
    assert exploration_weight(score=-EXPLORE_DAMP_SCALE, **kwargs) == pytest.approx(
        0.5 * exploration_weight(score=0.0, **kwargs)
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
    expected = squashed_base(1.0) + seasonality_bonus(recipe, today)
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
        squashed_base(0.5)
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
    expected = squashed_base(1_000_000) + recency_penalty(recipe, today)
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
    ) == pytest.approx(squashed_base(1.0))
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
        squashed_base(1.0)
        + 2 * seasonality_bonus(recipe, today)
        + 2 * recency_penalty(recipe, today)
        + 2 * bulk_bonus(recipe)
        + 2 * tag_penalty(recipe, {"spicy"})
    )


def test_tag_penalty():
    recipe = {"tags": ["spicy", "vegan"]}
    assert tag_penalty(recipe, {"spicy"}) == pytest.approx(-3.0)
    assert tag_penalty(recipe, {"gluten-free"}) == pytest.approx(0.0)


def test_bulk_bonus_uses_named_constant():
    recipe = {"bulk_prep": True}
    assert bulk_bonus(recipe) == pytest.approx(BULK_PREP_BONUS)
    assert bulk_bonus({"bulk_prep": False}) == pytest.approx(0.0)


def test_tag_penalty_default_uses_named_constant():
    recipe = {"tags": ["spicy"]}
    assert tag_penalty(recipe, {"spicy"}) == pytest.approx(-DEFAULT_TAG_PENALTY)


# ---------------------------------------------------------------------------
# Ingredient repetition penalty
# ---------------------------------------------------------------------------

def test_ingredient_repetition_penalty_empty_map_is_zero():
    recipe = {"ingredient_ids": [1, 2, 3]}
    assert ingredient_repetition_penalty(recipe, date(2024, 6, 1), {}) == 0.0


def test_ingredient_repetition_penalty_single_recent_decays():
    planning = date(2024, 6, 3)
    recipe = {"ingredient_ids": [1]}
    same_day = ingredient_repetition_penalty(recipe, planning, {1: date(2024, 6, 3)})
    one_day = ingredient_repetition_penalty(recipe, planning, {1: date(2024, 6, 2)})
    assert same_day == pytest.approx(-INGREDIENT_REPEAT_MAX_PENALTY)
    # ~1-day half-life: one day ago is roughly half the max penalty.
    expected_one = -INGREDIENT_REPEAT_MAX_PENALTY * math.exp(
        -math.log(2) * 1 / INGREDIENT_REPEAT_HALF_LIFE_DAYS
    )
    assert one_day == pytest.approx(expected_one)
    assert same_day < one_day < 0


def test_ingredient_repetition_penalty_sums_across_overlaps():
    planning = date(2024, 6, 3)
    one = {"ingredient_ids": [1]}
    three = {"ingredient_ids": [1, 2, 3]}
    used = {1: date(2024, 6, 3), 2: date(2024, 6, 3), 3: date(2024, 6, 3)}
    pen_one = ingredient_repetition_penalty(one, planning, used)
    pen_three = ingredient_repetition_penalty(three, planning, used)
    assert pen_three == pytest.approx(3 * pen_one)


def test_ingredient_repetition_penalty_zero_beyond_window():
    planning = date(2024, 6, 10)
    recipe = {"ingredient_ids": [1]}
    old = {1: planning - timedelta(days=int(INGREDIENT_REPEAT_WINDOW_DAYS))}
    assert ingredient_repetition_penalty(recipe, planning, old) == 0.0


def test_ingredient_repetition_penalty_future_is_zero():
    planning = date(2024, 6, 1)
    recipe = {"ingredient_ids": [1]}
    future = {1: date(2024, 6, 5)}
    assert ingredient_repetition_penalty(recipe, planning, future) == 0.0


# ---------------------------------------------------------------------------
# Tag repetition penalty
# ---------------------------------------------------------------------------

def test_tag_repetition_penalty_only_penalized_tags_count():
    planning = date(2024, 6, 3)
    recipe = {"tags": ["pasta", "vegetarian"]}
    used = {"pasta": date(2024, 6, 3), "vegetarian": date(2024, 6, 3)}
    penalized = {"pasta"}
    # Only "pasta" is penalized; "vegetarian" repetition is ignored.
    assert tag_repetition_penalty(recipe, planning, used, penalized) == pytest.approx(
        -TAG_REPEAT_MAX_PENALTY
    )


def test_tag_repetition_penalty_attribute_tag_repeated_is_zero():
    planning = date(2024, 6, 3)
    recipe = {"tags": ["vegetarian"]}
    used = {"vegetarian": date(2024, 6, 3)}
    assert tag_repetition_penalty(recipe, planning, used, {"pasta"}) == 0.0


def test_tag_repetition_penalty_format_tag_decays():
    planning = date(2024, 6, 3)
    recipe = {"tags": ["pasta"]}
    penalized = {"pasta"}
    same_day = tag_repetition_penalty(
        recipe, planning, {"pasta": date(2024, 6, 3)}, penalized
    )
    later = tag_repetition_penalty(
        recipe, planning, {"pasta": date(2024, 6, 1)}, penalized
    )
    expected_later = -TAG_REPEAT_MAX_PENALTY * math.exp(
        -math.log(2) * 2 / TAG_REPEAT_HALF_LIFE_DAYS
    )
    assert same_day == pytest.approx(-TAG_REPEAT_MAX_PENALTY)
    assert later == pytest.approx(expected_later)
    assert same_day < later < 0


# ---------------------------------------------------------------------------
# Fridge bonus
# ---------------------------------------------------------------------------

def test_fridge_bonus_overlap_returns_scale():
    recipe = {"ingredient_ids": [1, 2, 3]}
    assert fridge_bonus(recipe, {2, 9}) == pytest.approx(FRIDGE_BONUS_SCALE)


def test_fridge_bonus_no_overlap_is_zero():
    recipe = {"ingredient_ids": [1, 2, 3]}
    assert fridge_bonus(recipe, {9, 10}) == pytest.approx(0.0)


def test_fridge_bonus_empty_set_is_zero():
    recipe = {"ingredient_ids": [1, 2, 3]}
    assert fridge_bonus(recipe, set()) == pytest.approx(0.0)


def test_score_recipe_fridge_boost_raises_score():
    today = date(2024, 6, 1)
    recipe = {
        "score": 1.0,
        "ingredients": [{"season_months": [6]}],
        "ingredient_ids": [1, 2],
        "date_last_planned": date(2024, 4, 1),
        "bulk_prep": False,
    }
    without = score_recipe(recipe, today)
    with_fridge = score_recipe(recipe, today, fridge_ingredient_ids={2})
    assert with_fridge == pytest.approx(without + FRIDGE_BONUS_SCALE)


def test_score_recipe_backward_compatible_without_maps():
    today = date(2024, 6, 1)
    recipe = {
        "score": 1.0,
        "ingredients": [{"season_months": [6]}, {"season_months": [5, 6]}],
        "ingredient_ids": [1, 2],
        "tags": ["pasta"],
        "date_last_planned": date(2024, 4, 1),
        "bulk_prep": False,
    }
    baseline = squashed_base(1.0) + seasonality_bonus(recipe, today)
    assert score_recipe(recipe, today) == pytest.approx(baseline)


# ---------------------------------------------------------------------------
# Base score squash
# ---------------------------------------------------------------------------


def test_rejected_recipe_loses_to_neutral_one_despite_being_in_season():
    """Sustained rejection outweighs a full seasonality bonus.

    The regression this guards: with the base score squashed into a narrow
    range, a disliked recipe kept winning slots purely because it was in
    season, and no amount of rejecting it could dislodge it.
    """

    today = date(2024, 6, 1)
    long_ago = date(2024, 1, 1)
    # One heavily rejected recipe among nine untouched ones. The pool has to be
    # this wide because the normalisation is pool-relative: a lone outlier among
    # N recipes cannot exceed a z-score of -sqrt(N-1), so a 3-recipe pool could
    # not sink far enough to clear the +10 seasonality bonus however often it
    # was rejected.
    pool = [-8.0] + [0.0] * 9

    rejected = {
        "score": -8.0,
        "ingredients": [{"season_months": [6]}],  # fully in season: +10
        "date_last_planned": long_ago,
        "bulk_prep": False,
    }
    neutral = {
        "score": 0.0,
        "ingredients": [],  # no seasonal opinion either way
        "date_last_planned": long_ago,
        "bulk_prep": False,
    }

    assert score_recipe(rejected, today, base_scores=pool) < score_recipe(
        neutral, today, base_scores=pool
    )


def test_feedback_still_moves_the_score_past_the_old_saturation_point():
    """A recipe rejected twice as often scores meaningfully lower.

    ``tanh`` used to flatten at roughly four net rejections, after which
    further feedback changed the score by less than a tenth of a point.
    """

    today = date(2024, 6, 1)
    long_ago = date(2024, 1, 1)
    # mean 0, std 1 -> the normalised score equals the raw one.
    pool = [-1.0, 1.0]

    def at(raw_score):
        recipe = {
            "score": raw_score,
            "ingredients": [],
            "date_last_planned": long_ago,
            "bulk_prep": False,
        }
        return score_recipe(recipe, today, base_scores=pool)

    assert at(-2.0) - at(-4.0) > 1.0
