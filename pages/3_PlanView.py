"""Page to view the current meal plan."""

from __future__ import annotations

import streamlit as st

from mealplanner import crud


def main() -> None:
    """Render the current meal plan."""
    st.header("Plan View")
    plan = crud.get_plan()
    if not plan:
        st.info("No plan available.")
    else:
        for day, meals in plan.items():
            st.subheader(day)
            for meal in meals:
                st.markdown(f"- {meal}")


if __name__ == "__main__":
    main()