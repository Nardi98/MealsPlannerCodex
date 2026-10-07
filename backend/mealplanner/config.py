"""Default configuration for meal planner settings."""

from __future__ import annotations

from typing import Dict, Any

DEFAULT_PLAN_SETTINGS: Dict[str, Any] = {
    # Existing planner options
    "bulk_leftovers": True,
    "keep_days": 7,
    # Scoring weight persisted per user (edited from the profile, not per plan).
    "tag_penalty_weight": 1.0,
    # Leftover scheduling
    "LEFTOVER_REPEAT_DEFAULT": 1,
    "LEFTOVER_REPEAT_BY_RECIPE": {},
    "LEFTOVER_SPACING_GAP": 2,
    "MAX_LEFTOVERS_PER_DAY": 2,
    "LEFTOVER_DAYPART_PREF": {},
    "MEAL_NUMBER_TO_DAYPART": {1: "LUNCH", 2: "DINNER"},
    # Points a held leftover slot adds to its recipe: only a dish more than this
    # much better takes the slot (Q6).
    "LEFTOVER_HOLD_MARGIN": 15.0,
}

__all__ = ["DEFAULT_PLAN_SETTINGS"]
