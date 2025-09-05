"""Default configuration for meal planner settings."""

from __future__ import annotations

from typing import Dict, Any

DEFAULT_PLAN_SETTINGS: Dict[str, Any] = {
    # Existing planner options
    "bulk_leftovers": True,
    "keep_days": 7,
    # New leftover and scheduling parameters
    "LEFTOVER_REPEAT_DEFAULT": 1,
    "LEFTOVER_REPEAT_BY_RECIPE": {},
    "LEFTOVER_SPACING_GAP": 1,
    "MAX_LEFTOVERS_PER_DAY": 2,
    "MAX_LEFTOVERS_PER_WEEK": 7,
    "LEFTOVER_ACCEPT_WEIGHT": 1.0,
    "LEFTOVER_DAYPART_PREF": {},
    "LEFTOVER_DAYPART_WEIGHT": 1.0,
    "PROTECT_EXPLORE_SLOTS": False,
    "SOFT_HOLD_PENALTY": 1.0,
    "EXPLORE_PROTECTION_COST": 1.0,
    "MEAL_NUMBER_TO_DAYPART": {1: "LUNCH", 2: "DINNER"},
}

__all__ = ["DEFAULT_PLAN_SETTINGS"]
