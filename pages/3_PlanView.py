"""Page to view the current meal plan."""

from __future__ import annotations

import random
from datetime import date

import streamlit as st

from mealplanner import crud
from mealplanner.db import SessionLocal


def main() -> None:
    """Render the current meal plan."""
    st.header("Plan View")
    with SessionLocal() as session:
        plan = crud.get_plan(session)
    if not plan:
        st.info("No plan available.")
        return

    settings = crud.get_plan_settings()
    keep_days = int(settings.get("keep_days", 1))
    swap_slot = st.session_state.get("swap_slot")
    accepted = set(st.session_state.get("accepted_recipes", []))
    plan_items = list(plan.items())
    for day_idx, (day, meals) in enumerate(plan_items):
        st.subheader(day)
        try:
            day_date = date.fromisoformat(str(day))
        except ValueError:
            day_date = None
        for idx, meal in enumerate(meals):
            age: int | None = None
            if meal.endswith(" (leftover)") and day_date is not None:
                base = meal[:-11]
                for prev_idx in range(day_idx - 1, -1, -1):
                    prev_day, prev_meals = plan_items[prev_idx]
                    if base in prev_meals:
                        try:
                            prev_date = date.fromisoformat(str(prev_day))
                        except ValueError:
                            break
                        age = (day_date - prev_date).days
                        break
            if age is not None and age >= keep_days:
                st.warning(f"{meal} is {age} days old (max {keep_days})")

            cols = st.columns([3, 1, 1, 1])
            cols[0].markdown(f"- {meal}")
            key = f"{day}-{idx}"
            if key in accepted:
                cols[1].markdown(
                    "<button style='background-color: green; color: white; width: 100%' disabled>Accepted</button>",
                    unsafe_allow_html=True,
                )
            else:
                if cols[1].button("Accept", key=f"{key}-a"):
                    with SessionLocal() as session:
                        crud.accept_recipe(session, meal)
                    accepted.add(key)
                    st.session_state["accepted_recipes"] = list(accepted)
                    st.rerun()
                if cols[2].button("Reject", key=f"{key}-r"):
                    base = meal[:-11] if meal.endswith(" (leftover)") else meal
                    with SessionLocal() as session:
                        crud.reject_recipe(session, base)
                        options = crud.list_recipe_titles(session)
                    existing = {
                        m[:-11] if m.endswith(" (leftover)") else m
                        for meals in plan.values()
                        for m in meals
                    }
                    replacements = [r for r in options if r not in existing]
                    if replacements:
                        replacement = random.choice(replacements)
                        plan[day][idx] = replacement
                        crud.save_plan(plan)
                    st.rerun()
                if cols[3].button("Swap", key=f"{key}-s"):
                    st.session_state["swap_slot"] = (day, idx)
                    st.rerun()

    if swap_slot:
        day, idx = swap_slot
        with st.dialog("Swap Recipe"):
            with SessionLocal() as session:
                options = crud.list_recipe_titles(session)
            replacement = st.selectbox("Alternate Recipe", options)
            if st.button("Confirm Swap"):
                plan[day][idx] = replacement
                crud.save_plan(plan)
                st.session_state.pop("swap_slot", None)
                st.rerun()
            if st.button("Cancel"):
                st.session_state.pop("swap_slot", None)
                st.rerun()


if __name__ == "__main__":
    main()
