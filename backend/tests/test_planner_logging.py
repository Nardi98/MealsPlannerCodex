"""Generation explains itself through the slot trace, not through log noise."""

import logging
from datetime import date

from models import Recipe
from mealplanner.planner import generate_plan


def test_generation_emits_no_log_records(db_session, caplog):
    """The trace replaced the per-recipe DEBUG lines; nothing is logged."""
    db_session.add(Recipe(title="Good", score=1.0, course="main"))
    db_session.commit()
    with caplog.at_level(logging.DEBUG, logger="mealplanner"):
        slots = generate_plan(
            db_session, date(2024, 1, 1), days=1, meals_per_day=1, epsilon=0.0,
            return_slots=True,
        )
    assert caplog.records == []
    assert slots[0].trace["chosen"]["title"] == "Good"


def test_no_print_in_mealplanner_package():
    """No bare print() statements should remain in the mealplanner package."""
    import pathlib

    pkg = pathlib.Path(__file__).resolve().parents[1] / "mealplanner"
    offenders = []
    for path in pkg.glob("*.py"):
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("print(") or " print(" in stripped:
                offenders.append(f"{path.name}:{lineno}")
    assert not offenders, f"print() calls remain: {offenders}"
