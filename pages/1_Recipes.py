"""Recipes page for the Meals Planner Codex app."""

from __future__ import annotations

import streamlit as st

from mealplanner import crud


def main() -> None:
    """Render the recipes page."""
    st.header("Recipes")
    recipes = crud.get_recipes()
    if not recipes:
        st.info("No recipes available.")
    else:
        for recipe in recipes:
            st.markdown(f"- {recipe}")


if __name__ == "__main__":
    main()