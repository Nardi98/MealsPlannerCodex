"""New plan generation page."""

from __future__ import annotations

from datetime import date
import inspect

import streamlit as st

from mealplanner import crud, planner
from mealplanner.UIutils import spinner
from mealplanner.db import SessionLocal
from mealplanner.models import Recipe
from sqlalchemy import select


def clear_form() -> None:
    """Reset input widgets to their default values."""

    for key in [
        "start_date",
        "days",
        "meals_per_day",
        "epsilon",
        "seasonality_weight",
        "recency_weight",
        "tag_penalty_weight",
        "bulk_bonus_weight",
        "bulk_leftovers",
        "keep_days",
        "avoid_text",
        "reduce_text",
    ]:
        st.session_state.pop(key, None)


def main() -> None:
    """Render the page that creates a new meal plan."""
    st.header("New Plan")
    start_date = st.date_input("Start Date", value=date.today(), key="start_date")
    days = st.number_input(
        "Number of Days", min_value=1, value=7, step=1, key="days"
    )
    meals_per_day = st.number_input(
        "Meals per Day", min_value=1, value=1, step=1, key="meals_per_day"
    )
    with st.expander("Advanced Options"):
        epsilon = st.number_input(
            "ε",
            min_value=0.0,
            value=0.0,
            step=0.1,
            help="Randomness factor in plan generation",
            key="epsilon",
        )
        seasonality_weight = st.slider(
            "Seasonality Weight",
            min_value=0.0,
            max_value=2.0,
            value=1.0,
            step=0.1,
            help="Higher values prioritize seasonal recipes",
            key="seasonality_weight",
        )
        recency_weight = st.slider(
            "Recency Weight",
            min_value=0.0,
            max_value=2.0,
            value=1.0,
            step=0.1,
            help="Higher values avoid recently used recipes",
            key="recency_weight",
        )
        tag_penalty_weight = st.slider(
            "Tag Penalty Weight",
            min_value=0.0,
            max_value=2.0,
            value=1.0,
            step=0.1,
            help="Increase to penalize recipes with avoid tags",
            key="tag_penalty_weight",
        )
        bulk_bonus_weight = st.slider(
            "Bulk-Prep Bonus Weight",
            min_value=0.0,
            max_value=2.0,
            value=1.0,
            step=0.1,
            help="Increase to prefer recipes that can be bulk-prepped",
            key="bulk_bonus_weight",
        )
        bulk_leftovers = st.toggle(
            "Bulk Leftovers",
            value=True,
            help="Allow leftover portions from bulk-prepped meals",
            key="bulk_leftovers",
        )
        keep_days = st.number_input(
            "Keep Days",
            min_value=1,
            value=7,
            step=1,
            help="Number of days to retain planned meals",
            key="keep_days",
        )
        avoid_text = st.text_input(
            "Avoid Tags", help="Comma separated", key="avoid_text"
        )
        reduce_text = st.text_input(
            "Reduce Tags", help="Comma separated", key="reduce_text"
        )

    avoid_tags = [t.strip() for t in avoid_text.split(",") if t.strip()]
    reduce_tags = [t.strip() for t in reduce_text.split(",") if t.strip()]

    if st.button("Generate Plan"):
        try:
            with spinner("Generating plan..."):
                params = {
                    "start": start_date,
                    "days": int(days),
                    "meals_per_day": int(meals_per_day),
                    "epsilon": float(epsilon),
                    "avoid_tags": avoid_tags or None,
                    "reduce_tags": reduce_tags or None,
                    "seasonality_weight": float(seasonality_weight),
                    "recency_weight": float(recency_weight),
                    "tag_penalty_weight": float(tag_penalty_weight),
                    "bulk_bonus_weight": float(bulk_bonus_weight),
                    "bulk_leftovers": bool(bulk_leftovers),
                    "keep_days": int(keep_days),
                }
                if len(inspect.signature(planner.generate_plan).parameters) == 0:
                    plan = planner.generate_plan()
                    id_plan = {}
                else:
                    with SessionLocal() as session:
                        plan = planner.generate_plan(session, **params)
                        id_plan = {}
                        for day, meals in plan.items():
                            ids: list[int] = []
                            for meal in meals:
                                # ``scalar_one`` raises ``MultipleResultsFound`` if
                                # recipe titles are duplicated.  Fetch the first
                                # match instead to tolerate non-unique titles while
                                # still failing if none exist.
                                recipe_id = (
                                    session.execute(
                                        select(Recipe.id).where(Recipe.title == meal)
                                    )
                                    .scalars()
                                    .first()
                                )
                                if recipe_id is None:
                                    raise ValueError(f"Recipe '{meal}' not found")
                                ids.append(recipe_id)
                            id_plan[day] = ids
                        crud.set_meal_plan(session, start_date, id_plan)
                crud.save_plan(
                    plan,
                    bulk_leftovers=bool(bulk_leftovers),
                    keep_days=int(keep_days),
                )
        except Exception as exc:  # pragma: no cover - error path
            st.error(f"Failed to generate plan: {exc}")
        else:
            st.success("Plan generated successfully.")
            for day, meals in plan.items():
                st.subheader(day)
                for meal in meals:
                    st.markdown(f"- {meal}")
            st.button(
                "View Plan",
                on_click=lambda: st.switch_page("pages/3_PlanView.py"),
            )
            clear_form()


if __name__ == "__main__":
    main()
