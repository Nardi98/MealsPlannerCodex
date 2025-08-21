"""New plan generation page."""

from __future__ import annotations

import streamlit as st

from mealplanner import planner


def main() -> None:
    """Render the page that creates a new meal plan."""
    st.header("New Plan")
    if st.button("Generate Plan"):
        plan = planner.generate_plan()
        for day, meals in plan.items():
            st.subheader(day)
            for meal in meals:
                st.markdown(f"- {meal}")


if __name__ == "__main__":
    main()