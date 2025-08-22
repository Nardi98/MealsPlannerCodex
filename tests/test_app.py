"""Tests for Streamlit application pages."""

from __future__ import annotations

from streamlit.testing.v1 import AppTest


def test_main_runs() -> None:
    """The root application should render without error."""
    at = AppTest.from_file("app.py").run()
    assert at.title[0].value == "Meals Planner Codex"


def test_recipes_page(monkeypatch) -> None:
    """Recipes page displays data returned from the backend."""
    monkeypatch.setattr(
        "mealplanner.crud.get_recipes",
        lambda: ["Pasta", "Salad"],
    )
    at = AppTest.from_file("pages/1_Recipes.py").run()
    values = [m.value for m in at.markdown]
    assert any("Pasta" in v for v in values)
    assert any("Salad" in v for v in values)


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
        lambda: {"Tue": ["Pizza"]},
    )
    at = AppTest.from_file("pages/3_PlanView.py").run()
    sub_values = [h.value for h in at.subheader]
    assert "Tue" in sub_values
    md_values = [m.value for m in at.markdown]
    assert any("Pizza" in v for v in md_values)


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

