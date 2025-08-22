"""Page to view the current meal plan."""

from __future__ import annotations

import streamlit as st

from mealplanner import crud
from mealplanner.db import SessionLocal


def main() -> None:
    """Render the current meal plan."""
    st.header("Plan View")
    plan = crud.get_plan()
    if not plan:
        st.info("No plan available.")
        return

    swap_slot = st.session_state.get("swap_slot")
    for day, meals in plan.items():
        st.subheader(day)
        for idx, meal in enumerate(meals):
            cols = st.columns([3, 1, 1, 1])
            cols[0].markdown(f"- {meal}")
            if cols[1].button("Accept", key=f"{day}-{idx}-a"):
                with SessionLocal() as session:
                    crud.accept_recipe(session, meal)
                st.rerun()
            if cols[2].button("Reject", key=f"{day}-{idx}-r"):
                with SessionLocal() as session:
                    crud.reject_recipe(session, meal)
                st.rerun()
            if cols[3].button("Swap", key=f"{day}-{idx}-s"):
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
