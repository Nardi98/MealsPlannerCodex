import logging
from datetime import date

from mealplanner.models import Recipe
from mealplanner.planner import generate_plan


def _make_plan(db_session, caplog, level):
    good = Recipe(title="Good", servings_default=1, score=1.0, course="main")
    db_session.add(good)
    db_session.commit()
    with caplog.at_level(level, logger="mealplanner.planner"):
        generate_plan(
            db_session,
            date(2024, 1, 1),
            days=1,
            meals_per_day=1,
            epsilon=0.0,
        )
    return caplog


def test_generation_emits_debug_logs(db_session, caplog):
    """Generation should log diagnostics as DEBUG records, not print to stdout."""
    caplog = _make_plan(db_session, caplog, logging.DEBUG)
    debug_records = [r for r in caplog.records if r.levelno == logging.DEBUG]
    assert debug_records, "expected DEBUG log records from generation"
    assert all(r.name == "mealplanner.planner" for r in debug_records)


def test_generation_quiet_at_default_level(db_session, caplog):
    """No records should surface at WARNING level (default) during generation."""
    caplog = _make_plan(db_session, caplog, logging.WARNING)
    assert caplog.records == []


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
