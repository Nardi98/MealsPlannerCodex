"""New plan generation page."""

from __future__ import annotations

from datetime import date
import inspect

import streamlit as st

from mealplanner import crud, planner
from mealplanner.db import SessionLocal


def main() -> None:
    """Render the page that creates a new meal plan."""
    st.header("New Plan")
    start_date = st.date_input("Start Date", value=date.today())
    days = st.number_input("Number of Days", min_value=1, value=7, step=1)
    meals_per_day = st.number_input(
        "Meals per Day", min_value=1, value=1, step=1
    )
    epsilon = st.number_input("ε", min_value=0.0, value=0.0, step=0.1)
    tag_text = st.text_input("Tag Filters (comma separated)")
    tags = [t.strip() for t in tag_text.split(",") if t.strip()]

    if st.button("Generate Plan"):
        try:
            params = {
                "start": start_date,
                "days": int(days),
                "meals_per_day": int(meals_per_day),
                "epsilon": float(epsilon),
                "tags": tags or None,
            }
            if len(inspect.signature(planner.generate_plan).parameters) == 0:
                plan = planner.generate_plan()
            else:
                with SessionLocal() as session:
                    plan = planner.generate_plan(session, **params)
            crud.save_plan(plan)
            st.success("Plan generated successfully.")
            for day, meals in plan.items():
                st.subheader(day)
                for meal in meals:
                    st.markdown(f"- {meal}")
        except Exception as exc:  # pragma: no cover - error path
            st.error(f"Failed to generate plan: {exc}")


if __name__ == "__main__":
    main()
