"""The selection engine's stages, one at a time, with no database.

*candidates -> hard rules -> scoring -> selection* (FR-2): every test builds
plain :class:`Candidate` / :class:`SlotContext` values and calls one stage.
"""

import random
from datetime import date, timedelta

import pytest

from mealplanner import engine
from mealplanner.engine import Breakdown, Candidate, SlotContext
from mealplanner.scoring import RECENCY_MAX_PENALTY, recency_penalty

SLOT = date(2026, 10, 12)  # October


def cand(id, **kw):
    kw.setdefault("title", f"R{id}")
    return Candidate(id=id, **kw)


def ctx(**kw):
    kw.setdefault("date", SLOT)
    return SlotContext(**kw)


def reasons(candidates, context):
    _eligible, excluded = engine.hard_filter(candidates, context)
    return excluded


# --------------------------------------------------------------------------
# Hard rules
# --------------------------------------------------------------------------
def test_a_plain_candidate_is_eligible():
    eligible, excluded = engine.hard_filter([cand(1)], ctx())
    assert [c.id for c in eligible] == [1]
    assert excluded == {}


def test_excluded_ids_are_removed():
    assert reasons([cand(1)], ctx(exclude_ids={1})) == {1: "excluded"}


def test_avoid_tags_remove_the_candidate():
    assert reasons([cand(1, tags=("fried",))], ctx(avoid_tags={"fried"})) == {1: "avoid_tag"}


def test_a_fully_out_of_season_recipe_is_removed():
    summer = cand(1, ingredient_ids=(10,), ingredient_season_months=((6, 7, 8),))
    assert reasons([summer], ctx()) == {1: "out_of_season"}


def test_one_ingredient_in_season_keeps_the_recipe():
    mixed = cand(1, ingredient_ids=(10, 11), ingredient_season_months=((6, 7), ()))
    assert reasons([mixed], ctx()) == {}


@pytest.mark.parametrize("days_after", [0, 3])
def test_a_rejected_dish_is_banned_for_four_days_from_the_rejected_slot(days_after):
    rejected = cand(1, date_last_rejected=SLOT - timedelta(days=days_after))
    assert engine.BAN_DAYS == 4
    assert reasons([rejected], ctx()) == {1: "banned"}


@pytest.mark.parametrize("days_after", [4, -1])
def test_the_ban_does_not_reach_outside_its_window(days_after):
    rejected = cand(1, date_last_rejected=SLOT - timedelta(days=days_after))
    assert reasons([rejected], ctx()) == {}


def test_a_main_eaten_within_five_days_breaks_the_min_gap():
    assert engine.MIN_GAP_DAYS == 5
    recent = cand(1)
    eaten = {1: [SLOT - timedelta(days=4)]}
    assert reasons([recent], ctx(eaten_dates=eaten)) == {1: "min_gap"}


def test_the_min_gap_also_looks_forward():
    """A dish already planned two days later would repeat inside the gap."""
    eaten = {1: [SLOT + timedelta(days=2)]}
    assert reasons([cand(1)], ctx(eaten_dates=eaten)) == {1: "min_gap"}


def test_five_days_is_far_enough():
    eaten = {1: [SLOT - timedelta(days=5)]}
    assert reasons([cand(1)], ctx(eaten_dates=eaten)) == {}


def test_a_fridge_ingredient_overrides_the_min_gap():
    recent = cand(1, ingredient_ids=(10,), ingredient_season_months=((),))
    eaten = {1: [SLOT - timedelta(days=1)]}
    assert reasons([recent], ctx(eaten_dates=eaten, fridge_remaining={10: 1})) == {}


def test_a_strictly_seasonal_dish_overrides_the_min_gap():
    seasonal = cand(1, ingredient_ids=(10, 11), ingredient_season_months=((9, 10, 11), ()))
    eaten = {1: [SLOT - timedelta(days=1)]}
    assert reasons([seasonal], ctx(eaten_dates=eaten)) == {}


def test_without_the_min_gap_flag_recent_dishes_stay():
    """Sides get recency and the ban, but no minimum gap."""
    eaten = {1: [SLOT - timedelta(days=1)]}
    assert reasons([cand(1)], ctx(eaten_dates=eaten, min_gap=False)) == {}


def test_the_held_recipe_is_exempt_from_the_min_gap_on_its_slot():
    eaten = {1: [SLOT - timedelta(days=2)]}
    assert reasons([cand(1)], ctx(eaten_dates=eaten, held_recipe_id=1)) == {}


# --------------------------------------------------------------------------
# is_strictly_seasonal
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    "months, expected",
    [
        (((10,), ()), True),            # the one seasonal ingredient is in season
        (((10,), (11,)), False),        # a seasonal ingredient out of season
        (((), ()), False),              # no seasonal data at all
        ((tuple(range(1, 13)),), False),  # all-year is not seasonal data
    ],
)
def test_is_strictly_seasonal(months, expected):
    c = cand(1, ingredient_ids=tuple(range(len(months))), ingredient_season_months=months)
    assert engine.is_strictly_seasonal(c, 10) is expected


# --------------------------------------------------------------------------
# Scoring
# --------------------------------------------------------------------------
def test_the_breakdown_sums_to_its_total():
    c = cand(
        1, score=3.0, bulk_prep=True, tags=("pasta",), ingredient_ids=(10,),
        ingredient_season_months=((10,),),
    )
    context = ctx(
        eaten_dates={1: [SLOT - timedelta(days=8)]},
        ingredient_last_used={10: SLOT - timedelta(days=1)},
        tag_last_used={"pasta": SLOT - timedelta(days=1)},
        penalized_tags={"pasta"},
        reduce_tags={"pasta"},
        fridge_remaining={10: 1},
    )
    [(_, breakdown)] = engine.score_all([c, cand(2, score=-3.0)], context)[:1]

    assert list(breakdown.terms) == [
        "base", "seasonality", "recency", "bulk", "fridge", "reduce_tags",
        "ingredient_repeat", "tag_repeat", "hold",
    ]
    assert breakdown.total == pytest.approx(sum(breakdown.terms.values()))
    assert all(v != 0 for k, v in breakdown.terms.items() if k != "hold")


def test_weights_scale_their_terms():
    c = cand(1, bulk_prep=True)
    plain = engine.score(c, ctx(), engine.base_stats([c]))
    halved = engine.score(c, ctx(weights=engine.Weights(bulk_bonus=0.5)), engine.base_stats([c]))
    assert halved.terms["bulk"] == pytest.approx(plain.terms["bulk"] / 2)


def test_recency_uses_the_latest_meal_on_or_before_the_slot():
    """R5: a meal planned after the slot never hides an earlier one."""
    c = cand(1)
    context = ctx(eaten_dates={1: [SLOT - timedelta(days=2), SLOT + timedelta(days=1)]})
    breakdown = engine.score(c, context, engine.base_stats([c]))
    expected = recency_penalty({"date_last_planned": SLOT - timedelta(days=2)}, SLOT)
    assert breakdown.terms["recency"] == pytest.approx(expected)
    assert expected < 0


def test_never_eaten_means_no_recency_penalty():
    c = cand(1)
    assert engine.score(c, ctx(), engine.base_stats([c])).terms["recency"] == 0


def test_the_held_recipe_gets_the_hold_term_and_others_do_not():
    held, other = cand(1), cand(2)
    context = ctx(held_recipe_id=1, hold_margin=15.0)
    stats = engine.base_stats([held, other])
    assert engine.score(held, context, stats).terms["hold"] == 15.0
    assert engine.score(other, context, stats).terms["hold"] == 0.0


def test_the_held_recipe_is_exempt_from_its_own_repetition_terms():
    held = cand(1, tags=("soup",), ingredient_ids=(10,), ingredient_season_months=((),))
    context = ctx(
        held_recipe_id=1,
        eaten_dates={1: [SLOT - timedelta(days=1)]},
        ingredient_last_used={10: SLOT - timedelta(days=1)},
        tag_last_used={"soup": SLOT - timedelta(days=1)},
        penalized_tags={"soup"},
    )
    terms = engine.score(held, context, engine.base_stats([held])).terms
    assert (terms["recency"], terms["ingredient_repeat"], terms["tag_repeat"]) == (0, 0, 0)

    # The same history does count against a recipe on a slot it does not hold.
    unheld = engine.score(held, ctx(**{**context.__dict__, "held_recipe_id": None}),
                          engine.base_stats([held])).terms
    assert unheld["recency"] == pytest.approx(-RECENCY_MAX_PENALTY / 2 ** 0.25)


# --------------------------------------------------------------------------
# Selection
# --------------------------------------------------------------------------
def _scored(*pairs):
    return [(c, Breakdown({"base": total})) for c, total in pairs]


def test_argmax_wins_without_exploration():
    a, b = cand(1), cand(2)
    choice = engine.select(_scored((a, 1.0), (b, 2.0)), ctx(), 0.0, random.Random(0))
    assert (choice.candidate.id, choice.rank, choice.mode) == (2, 0, "exploit")


@pytest.mark.parametrize("gap, winner", [(14.9, 1), (15.1, 2)])
def test_a_held_slot_falls_only_to_a_dish_more_than_the_margin_better(gap, winner):
    held, fresh = cand(1), cand(2)
    context = ctx(held_recipe_id=1, hold_margin=15.0)
    stats = engine.base_stats([held, fresh])
    held_total = engine.score(held, context, stats).total
    scored = [
        (held, engine.score(held, context, stats)),
        (fresh, Breakdown({"base": held_total - 15.0 + gap})),
    ]
    assert engine.select(scored, context, 0.0, random.Random(0)).candidate.id == winner


def test_exploration_draws_with_the_injected_rng_by_explore_weight():
    top = cand(1)
    kept = cand(2)                       # kept 2 days ago: weight 0
    stale = cand(3)                      # never suggested: weight 365
    context = ctx(kept_dates={1: [SLOT - timedelta(days=1)], 2: [SLOT - timedelta(days=2)]})
    scored = _scored((top, 9.0), (kept, 5.0), (stale, 1.0))

    choice = engine.select(scored, context, 1.0, random.Random(42))

    assert choice.mode == "explore"
    assert choice.candidate.id == 3
    assert choice.rank == 2
    assert choice.explore_weights == {1: 0.0, 2: 0.0, 3: 365.0}


def test_the_same_seed_draws_the_same_dish():
    scored = _scored(*((cand(i), float(i)) for i in range(1, 30)))
    picks = {engine.select(scored, ctx(), 1.0, random.Random(7)).candidate.id for _ in range(5)}
    assert len(picks) == 1


def test_exploration_falls_back_to_uniform_when_every_weight_is_zero():
    a, b = cand(1), cand(2)
    context = ctx(kept_dates={1: [SLOT], 2: [SLOT]})
    choice = engine.select(_scored((a, 1.0), (b, 2.0)), context, 1.0, random.Random(1))
    assert choice.mode == "explore"
    assert choice.candidate.id in {1, 2}


def test_select_never_touches_the_global_random(monkeypatch):
    def boom(*_a, **_k):
        raise AssertionError("global random used")

    for name in ("random", "choices", "randrange", "choice"):
        monkeypatch.setattr(random, name, boom)
    scored = _scored((cand(1), 1.0), (cand(2), 2.0))
    engine.select(scored, ctx(), 1.0, random.Random(3))
