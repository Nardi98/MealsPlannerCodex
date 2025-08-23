"""Page to view the current meal plan."""

from __future__ import annotations

import random
from datetime import date

import streamlit as st

from mealplanner import crud
from mealplanner.db import SessionLocal
from mealplanner.models import Recipe
from sqlalchemy import select


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
    accepted = set(settings.get("accepted_recipes", []))
    accepted.update(st.session_state.get("accepted_recipes", []))
    st.session_state["accepted_recipes"] = list(accepted)
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
            accept_clicked = cols[1].button("Accept", key=f"{key}-a")
            reject_clicked = cols[2].button("Reject", key=f"{key}-r")
            swap_clicked = cols[3].button("Swap", key=f"{key}-s")
            if key in accepted:
                cols[1].markdown(
                    f"<style>div[data-testid='stButton'][data-key='{key}-a'] > button {{background-color: green; color: white;}}</style>",
                    unsafe_allow_html=True,
                )
            if accept_clicked and key not in accepted:
                with SessionLocal() as session:
                    crud.accept_recipe(session, meal)
                accepted.add(key)
                st.session_state['accepted_recipes'] = list(accepted)
                crud.save_plan(plan, accepted_recipes=list(accepted))
                st.rerun()
            if reject_clicked:
                base = meal[:-11] if meal.endswith(" (leftover)") else meal
                with SessionLocal() as session:
                    if key in accepted:
                        crud.reject_recipe(session, base)
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
                        id_plan: dict[str, list[int]] = {}
                        for d, meals in plan.items():
                            ids: list[int] = []
                            for title in meals:
                                title_base = (
                                    title[:-11] if title.endswith(" (leftover)") else title
                                )
                                rid = (
                                    session.execute(
                                        select(Recipe.id).where(Recipe.title == title_base)
                                    )
                                    .scalars()
                                    .first()
                                )
                                if rid is not None:
                                    ids.append(rid)
                            id_plan[d] = ids
                        try:
                            plan_date = date.fromisoformat(next(iter(plan)))
                        except Exception:
                            plan_date = date.today()
                        crud.set_meal_plan(session, plan_date, id_plan)
                if key in accepted:
                    accepted.remove(key)
                st.session_state['accepted_recipes'] = list(accepted)
                crud.save_plan(plan, accepted_recipes=list(accepted))
                st.rerun()
            if swap_clicked:
                st.session_state['swap_slot'] = (day, idx)
                st.rerun()

    if swap_slot:
        day, idx = swap_slot

        @st.dialog("Swap Recipe")
        def swap_dialog(d: str, i: int) -> None:
            """Display recipe search and handle swapping the meal."""

            with SessionLocal() as session:
                options = crud.list_recipe_titles(session)

            query = st.text_input("Search Recipe")
            matches = [o for o in options if o.lower().startswith(query.lower())]
            replacement = (
                st.selectbox("Alternate Recipe", matches) if matches else None
            )

            if st.button("Confirm Swap") and replacement:
                plan[d][i] = replacement
                with SessionLocal() as session:
                    # Persist the updated plan and mark the recipe as accepted
                    id_plan: dict[str, list[int]] = {}
                    for day_name, meals in plan.items():
                        ids: list[int] = []
                        for title in meals:
                            title_base = (
                                title[:-11] if title.endswith(" (leftover)") else title
                            )
                            rid = (
                                session.execute(
                                    select(Recipe.id).where(Recipe.title == title_base)
                                )
                                .scalars()
                                .first()
                            )
                            if rid is not None:
                                ids.append(rid)
                        id_plan[day_name] = ids
                    try:
                        plan_date = date.fromisoformat(next(iter(plan)))
                    except Exception:
                        plan_date = date.today()
                    crud.set_meal_plan(session, plan_date, id_plan)
                    crud.accept_recipe(session, replacement)

                key = f"{d}-{i}"
                accepted.add(key)
                st.session_state["accepted_recipes"] = list(accepted)
                crud.save_plan(plan, accepted_recipes=list(accepted))
                st.session_state.pop("swap_slot", None)
                st.rerun()

            if st.button("Cancel"):
                st.session_state.pop("swap_slot", None)
                st.rerun()

        swap_dialog(day, idx)


if __name__ == "__main__":
    main()
