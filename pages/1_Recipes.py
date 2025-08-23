"""Recipe management page for the Meals Planner Codex app."""

from __future__ import annotations

from typing import Dict, List, Optional

import time
import streamlit as st
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from mealplanner import crud
from mealplanner.UIUtils import combobox_with_add
from mealplanner.db import SessionLocal, init_db
from mealplanner.models import Ingredient, Recipe, Tag


TAG_STYLE = """
<style>
.recipe-tag {
    display: inline-block;
    padding: 0.125rem 0.5rem;
    border-radius: 0.25rem;
    background-color: var(--primary-color);
    color: white;
    font-size: 0.8rem;
    margin-left: 0.25rem;
}
</style>
"""

ALLOWED_UNITS = ["g", "l", "ml", "pieces"]


def _render_tag_boxes(tags: List[str]) -> str:
    """Return HTML for displaying tag names as colored boxes."""

    return "".join(f"<span class='recipe-tag'>{t}</span>" for t in tags)


def _render_tag_filter(session: Session) -> List[str]:
    """Render a multiselect for filtering recipes by tags.

    Returns a list with the currently selected tag names.
    """

    tags = session.execute(select(Tag).order_by(Tag.name)).scalars().all()
    if "selected_tags" not in st.session_state:
        st.session_state["selected_tags"] = []

    tag_names = [t.name for t in tags]
    selected: List[str] = st.multiselect(
        "Filter by Tag", tag_names, key="selected_tags"
    )

    return selected


def _render_recipe_fields(
    session: Session, prefix: str, recipe: Optional[Recipe] = None
) -> Dict[str, object]:
    """Render form fields for creating or editing a recipe."""

    title = st.text_input(
        "Title", value=getattr(recipe, "title", ""), key=f"{prefix}_title"
    )
    servings = st.number_input(
        "Servings",
        min_value=1,
        step=1,
        value=getattr(recipe, "servings_default", 1),
        key=f"{prefix}_servings",
    )
    procedure = st.text_area(
        "Procedure", value=getattr(recipe, "procedure", ""), key=f"{prefix}_procedure"
    )
    bulk_prep = st.checkbox(
        "Suitable for bulk preparation",
        value=getattr(recipe, "bulk_prep", False),
        key=f"{prefix}_bulk_prep",
    )

    # Tag selection
    tags_stmt = select(Tag).order_by(Tag.name)
    all_tags = session.execute(tags_stmt).scalars().all()
    tag_names = [t.name for t in all_tags]
    default_tags = [t.name for t in getattr(recipe, "tags", [])]
    selected_tag_names = st.multiselect(
        "Tags", tag_names, default_tags, key=f"{prefix}_tags"
    )
    new_tag_names = st.text_input(
        "New tags (comma-separated)", key=f"{prefix}_new_tags"
    )
    selected_tags = [t for t in all_tags if t.name in selected_tag_names]

    # Ingredient inputs
    existing = list(getattr(recipe, "ingredients", []))
    rows_key = f"{prefix}_ingredient_rows"
    next_key = f"{rows_key}_next"
    if rows_key not in st.session_state:
        st.session_state[rows_key] = list(range(len(existing)))
        st.session_state[next_key] = len(existing)

    # Button to dynamically add ingredient rows. Each click triggers a rerun
    # to display the updated set of inputs.
    if st.button("➕", key=f"{prefix}_add_ingredient"):
        row_id = st.session_state[next_key]
        st.session_state[next_key] += 1
        st.session_state[rows_key].append(row_id)
        st.rerun()

    ingredient_rows = st.session_state[rows_key]

    def fetch_ingredient_options(query: str) -> List[str]:
        stmt = select(Ingredient.name).distinct().order_by(Ingredient.name)
        if query:
            stmt = stmt.where(Ingredient.name.ilike(f"%{query}%"))
        return session.execute(stmt).scalars().all()

    ingredients: List[Ingredient] = []
    for pos, row_id in enumerate(ingredient_rows):
        ing = existing[row_id] if row_id < len(existing) else None
        cols = st.columns(5)
        with cols[0]:
            if st.button("✖", key=f"{prefix}_del_ing_{row_id}"):
                ingredient_rows.remove(row_id)
                for suffix in ("name", "qty", "unit", "season"):
                    st.session_state.pop(f"{prefix}_ing_{row_id}_{suffix}", None)
                st.rerun()
        name_key = f"{prefix}_ing_{row_id}_name"

        placeholder = getattr(ing, "name", f"Ingredient {pos + 1}")
        with cols[1]:
            name_val, _ = combobox_with_add(
                key=name_key,
                placeholder=placeholder,
                fetch_options=fetch_ingredient_options,
                allow_create=True,
            )
        if not name_val and ing:
            name_val = ing.name

        quantity = cols[2].number_input(
            f"Qty {pos + 1}",
            min_value=0.0,
            step=1.0,
            value=getattr(ing, "quantity", 0.0) or 0.0,
            key=f"{prefix}_ing_{row_id}_qty",
        )
        unit_options = ALLOWED_UNITS
        current_unit = getattr(ing, "unit", "")
        unit_index = (
            unit_options.index(current_unit) if current_unit in unit_options else 0
        )
        unit = cols[3].selectbox(
            f"Unit {pos + 1}",
            unit_options,
            index=unit_index,
            key=f"{prefix}_ing_{row_id}_unit",
        )
        season = cols[4].text_input(
            f"Season {pos + 1}",
            value=getattr(ing, "season_months", ""),
            key=f"{prefix}_ing_{row_id}_season",
        )
        if name_val:
            ingredients.append(
                Ingredient(
                    name=name_val, quantity=quantity, unit=unit, season_months=season
                )
            )

    if new_tag_names:
        for raw_name in new_tag_names.split(","):
            name = raw_name.strip()
            if name:
                selected_tags.append(crud.get_or_create_tag(session, name))

    return {
        "title": title,
        "servings_default": int(servings),
        "procedure": procedure,
        "bulk_prep": bulk_prep,
        "ingredients": ingredients,
        "tags": selected_tags,
    }


def _refresh() -> None:
    """Trigger a Streamlit rerun to refresh the page."""

    st.rerun()


def _clear_form_state(prefix: str) -> None:
    """Remove any widget state associated with a form prefix.

    Streamlit persists widget values across reruns via ``st.session_state``.
    When creating a new recipe we want a clean form after the page refresh,
    so all keys that start with the given prefix are deleted before calling
    :func:`_refresh`.
    """

    to_delete = [k for k in st.session_state if k.startswith(f"{prefix}_")]
    for key in to_delete:
        del st.session_state[key]


def main() -> None:
    """Render the recipes page with CRUD operations."""
    if toast := st.session_state.pop("toast", None):
        toast_msg = st.toast(toast)
        time.sleep(1.5)
        toast_msg.empty()

    st.header("Recipes")
    st.markdown(TAG_STYLE, unsafe_allow_html=True)
    init_db()
    session = SessionLocal()

    with st.expander("Create Recipe"):
        data = _render_recipe_fields(session, "create")
        if st.button("Create", key="create_recipe_submit"):
            crud.create_recipe(session, **data)
            st.session_state["toast"] = "Recipe created"
            _clear_form_state("create")
            _refresh()

    selected_tags = _render_tag_filter(session)

    recipes = (
        session.execute(
            select(Recipe)
            .options(selectinload(Recipe.tags))
            .order_by(Recipe.title)
        )
        .scalars()
        .all()
    )

    if selected_tags:
        selected_set = set(selected_tags)
        recipes = [
            r for r in recipes if selected_set.issubset({t.name for t in r.tags})
        ]

    if not recipes:
        st.info("No recipes available.")

    for recipe in recipes:
        tag_html = _render_tag_boxes([t.name for t in recipe.tags])
        exp_col, tag_col = st.columns([4, 1])
        with exp_col:
            with st.expander(recipe.title):
                data = _render_recipe_fields(session, f"edit_{recipe.id}", recipe)
                if st.button("Update", key=f"update_{recipe.id}"):
                    crud.update_recipe(session, recipe.id, **data)
                    st.session_state["toast"] = "Recipe updated"
                    _refresh()
                if st.button("Delete", key=f"delete_{recipe.id}"):
                    crud.delete_recipe(session, recipe.id)
                    st.session_state["toast"] = "Recipe deleted"
                    _refresh()
        with tag_col:
            if tag_html:
                st.markdown(tag_html, unsafe_allow_html=True)

    session.close()


if __name__ == "__main__":
    main()

