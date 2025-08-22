"""Tests for Streamlit application pages."""

from __future__ import annotations

from streamlit.testing.v1 import AppTest
from mealplanner import crud
from mealplanner.db import SessionLocal, init_db


def test_main_runs() -> None:
    """The root application should render without error."""
    at = AppTest.from_file("app.py").run()
    assert at.title[0].value == "Meals Planner Codex"


def test_recipes_page() -> None:
    """Recipes page displays existing recipes."""
    init_db()
    with SessionLocal() as session:
        crud.create_recipe(session, title="Pasta", servings_default=1)
        crud.create_recipe(session, title="Salad", servings_default=1)
    at = AppTest.from_file("pages/1_Recipes.py").run()
    labels = [e.label for e in at.expander]
    assert any("Pasta" in l for l in labels)
    assert any("Salad" in l for l in labels)


def test_new_plan_page(monkeypatch) -> None:
    """Generating a new plan reflects mocked planner output."""
    monkeypatch.setattr(
        "mealplanner.planner.generate_plan",
        lambda: {"Mon": ["Soup"]},
    )
    at = AppTest.from_file("pages/2_NewPlan.py").run()
    at.button[0].click().run()
    values = [m.value for m in at.markdown]
    assert any("Soup" in v for v in values)


def test_plan_view_page(monkeypatch) -> None:
    """Viewing the plan shows data from the mocked CRUD layer."""
    monkeypatch.setattr(
        "mealplanner.crud.get_plan",
        lambda *a, **k: {"Tue": ["Pizza"]},
    )
    monkeypatch.setattr(
        "mealplanner.crud.list_recipe_titles", lambda *a, **k: ["Pizza"]
    )
    calls: list[str] = []
    monkeypatch.setattr(
        "mealplanner.crud.accept_recipe", lambda *a, **k: calls.append("a")
    )
    monkeypatch.setattr(
        "mealplanner.crud.reject_recipe", lambda *a, **k: calls.append("r")
    )
    at = AppTest.from_file("pages/3_PlanView.py").run()
    sub_values = [h.value for h in at.subheader]
    assert "Tue" in sub_values
    md_values = [m.value for m in at.markdown]
    assert any("Pizza" in v for v in md_values)

    at.button[0].click().run()
    assert "a" in calls

    at = AppTest.from_file("pages/3_PlanView.py").run()
    at.button[1].click().run()
    assert "r" in calls


def test_plan_view_expired_leftover_warning(monkeypatch) -> None:
    """Expired leftovers should trigger a warning in the plan view."""
    plan = {
        "2024-01-01": ["Bulk"],
        "2024-01-03": ["Bulk (leftover)"],
    }
    crud.save_plan(plan, keep_days=2)
    monkeypatch.setattr("mealplanner.crud.get_plan", lambda *a, **k: plan)
    monkeypatch.setattr(
        "mealplanner.crud.list_recipe_titles", lambda *a, **k: ["Bulk"]
    )
    try:
        at = AppTest.from_file("pages/3_PlanView.py").run()
        warnings = [w.value for w in at.warning]
        assert any("days old" in w for w in warnings)
    finally:
        crud._PLAN_SETTINGS.clear()
        crud._PLAN_CACHE.clear()


def test_export_page(monkeypatch) -> None:
    """Export button displays data returned by the backend."""
    monkeypatch.setattr(
        "mealplanner.crud.export_data",
        lambda: "exported",
    )
    at = AppTest.from_file("pages/4_ImportExport.py").run()
    at = at.button[0].click().run()
    code_values = [c.value for c in at.code]
    assert any("exported" in v for v in code_values)

