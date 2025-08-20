"""Planning service stub.

The real planner will implement the scheduling algorithm described in the
specification.  For now this module exposes a minimal function that can be
expanded later.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Dict, List


@dataclass
class PlanRequest:
    start_date: date
    days: int
    meals_per_day: List[str]


def generate_empty_plan(req: PlanRequest) -> Dict[date, Dict[str, None]]:
    """Generate an empty plan grid for the requested period.

    Each day maps to a dictionary keyed by meal name with ``None`` values,
    ready to be populated with recipe assignments.
    """
    plan: Dict[date, Dict[str, None]] = {}
    for offset in range(req.days):
        d = req.start_date + timedelta(days=offset)
        plan[d] = {meal: None for meal in req.meals_per_day}
    return plan
