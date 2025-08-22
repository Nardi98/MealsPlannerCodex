"""Recipe management page for the Meals Planner Codex app."""

from __future__ import annotations

from typing import Dict, List, Optional

import streamlit as st
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from mealplanner import crud
from mealplanner.db import SessionLocal, init_db
from mealplanner.models import Ingredient, Recipe, Tag


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
    num_ing = int(
        st.number_input(
            "Number of ingredients",
            min_value=0,
            value=len(existing) if existing else 0,
            step=1,
            key=f"{prefix}_num_ing",
        )
    )

    ingredients: List[Ingredient] = []
    for idx in range(num_ing):
        ing = existing[idx] if idx < len(existing) else None
        cols = st.columns(4)
        name = cols[0].text_input(
            f"Name {idx + 1}", value=getattr(ing, "name", ""), key=f"{prefix}_ing_{idx}_name"
        )
        quantity = cols[1].number_input(
            f"Qty {idx + 1}",
            value=getattr(ing, "quantity", 0.0) or 0.0,
            key=f"{prefix}_ing_{idx}_qty",
        )
        unit = cols[2].text_input(
            f"Unit {idx + 1}", value=getattr(ing, "unit", ""), key=f"{prefix}_ing_{idx}_unit"
        )
        season = cols[3].text_input(
            f"Season {idx + 1}",
            value=getattr(ing, "season_months", ""),
            key=f"{prefix}_ing_{idx}_season",
        )
        if name:
            ingredients.append(
                Ingredient(name=name, quantity=quantity, unit=unit, season_months=season)
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
        "ingredients": ingredients,
        "tags": selected_tags,
    }


def _refresh() -> None:
    """Trigger a Streamlit rerun to refresh the page."""

    st.rerun()


def main() -> None:
    """Render the recipes page with CRUD operations."""

    st.header("Recipes")
    init_db()
    session = SessionLocal()

    with st.expander("Create Recipe"):
        with st.form("create_recipe_form"):
            data = _render_recipe_fields(session, "create")
            if st.form_submit_button("Create"):
                crud.create_recipe(session, **data)
                _refresh()

    # Retrieve recipe names using helper for compatibility with tests
    names = crud.get_recipes()

    recipes = (
        session.execute(
            select(Recipe)
            .options(selectinload(Recipe.tags))
            .order_by(Recipe.title)
        )
        .scalars()
        .all()
    )

    tag_map = {r.title: ", ".join(t.name for t in r.tags) for r in recipes}

    if names:
        for name in names:
            tags = tag_map.get(name)
            label = f" ({tags})" if tags else ""
            st.markdown(f"- {name}{label}")
    else:
        st.info("No recipes available.")

    for recipe in recipes:
        header_tags = ", ".join(t.name for t in recipe.tags)
        header = f"{recipe.title} ({header_tags})" if header_tags else recipe.title
        with st.expander(header):
            with st.form(f"edit_{recipe.id}"):
                data = _render_recipe_fields(session, f"edit_{recipe.id}", recipe)
                if st.form_submit_button("Update"):
                    crud.update_recipe(session, recipe.id, **data)
                    _refresh()
            if st.button("Delete", key=f"delete_{recipe.id}"):
                crud.delete_recipe(session, recipe.id)
                _refresh()

    session.close()


if __name__ == "__main__":
    main()

