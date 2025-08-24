"""FastAPI application for Meals Planner Codex."""
from __future__ import annotations

import io
import json
from datetime import date
from typing import Any, Dict, List, Optional
import random

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

import crud
import models
import schemas
from mealplanner import planner
from database import SessionLocal, engine

# Ensure database tables exist on startup
models.Base.metadata.create_all(bind=engine)

app = FastAPI()

# Allow all CORS for demo purposes
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    """Redirect the index route to the interactive API docs."""
    return RedirectResponse(url="/docs")


@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> Response:
    """Return an empty response for browsers requesting a favicon."""
    return Response(status_code=204)


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/recipes", response_model=List[schemas.RecipeOut])
def read_recipes(db: Session = Depends(get_db)) -> List[schemas.RecipeOut]:
    stmt = select(models.Recipe).options(
        selectinload(models.Recipe.tags),
        selectinload(models.Recipe.recipe_ingredients).selectinload(
            models.RecipeIngredient.ingredient
        ),
    )
    return db.execute(stmt).scalars().all()


def _payload_to_data(payload: schemas.RecipeIn, db: Session) -> dict:
    tags = [crud.get_or_create_tag(db, name) for name in payload.tags]
    existing = {
        ing.name: ing for ing in db.execute(select(models.Ingredient)).scalars()
    }
    recipe_ingredients: list[models.RecipeIngredient] = []
    for ing in payload.ingredients:
        ingredient = existing.get(ing.name)
        if ingredient is None:
            ingredient = models.Ingredient(
                name=ing.name,
                unit=ing.unit,
                season_months=ing.season_months,
            )
            db.add(ingredient)
            existing[ing.name] = ingredient
        recipe_ingredients.append(
            models.RecipeIngredient(ingredient=ingredient, quantity=ing.quantity)
        )
    return {
        "title": payload.title,
        "servings_default": payload.servings_default,
        "procedure": payload.procedure,
        "bulk_prep": payload.bulk_prep,
        "tags": tags,
        "recipe_ingredients": recipe_ingredients,
    }


@app.post("/recipes", response_model=schemas.RecipeOut, status_code=201)
def create_recipe(payload: schemas.RecipeIn, db: Session = Depends(get_db)) -> schemas.RecipeOut:
    data = _payload_to_data(payload, db)
    return crud.create_recipe(db, **data)


@app.put("/recipes/{recipe_id}", response_model=schemas.RecipeOut)
def update_recipe(
    recipe_id: int, payload: schemas.RecipeIn, db: Session = Depends(get_db)
) -> schemas.RecipeOut:
    data = _payload_to_data(payload, db)
    recipe = crud.update_recipe(db, recipe_id, **data)
    if recipe is None:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return recipe


@app.delete("/recipes/{recipe_id}", status_code=204)
def delete_recipe_route(recipe_id: int, db: Session = Depends(get_db)) -> Response:
    deleted = crud.delete_recipe(db, recipe_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return Response(status_code=204)


@app.delete("/recipes/{recipe_id}", status_code=204)
def delete_recipe(recipe_id: int, db: Session = Depends(get_db)) -> Response:
    recipe = db.get(models.Recipe, recipe_id)
    if recipe is None:
        raise HTTPException(status_code=404, detail="Recipe not found")
    db.delete(recipe)
    db.commit()
    return Response(status_code=204)


@app.get("/tags", response_model=List[schemas.TagOut])
def read_tags(db: Session = Depends(get_db)) -> List[schemas.TagOut]:
    return db.execute(select(models.Tag)).scalars().all()


@app.get("/ingredients", response_model=List[str])
def search_ingredients(search: str = "", db: Session = Depends(get_db)) -> List[str]:
    stmt = select(models.Ingredient.name).distinct().order_by(models.Ingredient.name)
    if search:
        stmt = stmt.where(models.Ingredient.name.ilike(f"{search}%"))
    return db.execute(stmt.limit(10)).scalars().all()


@app.get("/plan", response_model=Dict[str, List[str]])
@app.get("/meal-plans", response_model=Dict[str, List[str]])
def get_plan(plan_date: date | None = None, db: Session = Depends(get_db)) -> Dict[str, List[str]]:
    return crud.get_plan(db, plan_date)


@app.post("/plan", response_model=Dict[str, List[str]])
@app.post("/meal-plans", response_model=Dict[str, List[str]])
def set_plan(payload: schemas.MealPlanCreate, db: Session = Depends(get_db)) -> Dict[str, List[str]]:
    crud.set_meal_plan(db, payload.plan_date, payload.plan)
    title_plan: Dict[str, List[str]] = {}
    for day, ids in payload.plan.items():
        titles: List[str] = []
        for rid in ids:
            recipe = db.get(models.Recipe, rid)
            if recipe is not None:
                titles.append(recipe.title)
        title_plan[day] = titles
    crud.save_plan(
        title_plan,
        bulk_leftovers=payload.bulk_leftovers,
        keep_days=payload.keep_days,
    )
    return crud.get_plan(db, payload.plan_date)


@app.get("/plan/settings", response_model=Dict[str, Any])
def plan_settings() -> Dict[str, Any]:
    """Return metadata about the current plan such as ``keep_days``."""

    return crud.get_plan_settings()


@app.post("/feedback/accept")
def feedback_accept(
    payload: schemas.FeedbackIn, db: Session = Depends(get_db)
) -> Dict[str, str]:
    """Record user acceptance of a recipe."""

    if crud.accept_recipe(db, payload.title) is None:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return {"status": "ok"}


@app.post("/feedback/reject")
def feedback_reject(
    payload: schemas.FeedbackIn, db: Session = Depends(get_db)
) -> Dict[str, Optional[str]]:
    """Record user rejection of a recipe and suggest a replacement."""

    if crud.reject_recipe(db, payload.title) is None:
        raise HTTPException(status_code=404, detail="Recipe not found")
    existing = {
        m[:-11] if m.endswith(" (leftover)") else m
        for meals in crud.get_plan().values()
        for m in meals
    }
    existing.add(payload.title)
    available = list(set(crud.list_recipe_titles(db)) - existing)
    replacement = random.choice(available) if available else None
    return {"replacement": replacement}


@app.post("/meal-plans/generate")
def generate_plan_endpoint(
    payload: schemas.MealPlanGenerate, db: Session = Depends(get_db)
) -> Dict[str, List[Dict[str, object]]]:
    plan_titles = planner.generate_plan(
        db,
        start=payload.start,
        days=payload.days,
        meals_per_day=payload.meals_per_day,
        keep_days=payload.keep_days,
        bulk_leftovers=payload.bulk_leftovers,
        epsilon=payload.epsilon,
        avoid_tags=payload.avoid_tags,
        reduce_tags=payload.reduce_tags,
        seasonality_weight=payload.seasonality_weight,
        recency_weight=payload.recency_weight,
        tag_penalty_weight=payload.tag_penalty_weight,
        bulk_bonus_weight=payload.bulk_bonus_weight,
    )
    result: Dict[str, List[Dict[str, object]]] = {}
    for day, titles in plan_titles.items():
        items: List[Dict[str, object]] = []
        for title in titles:
            base = title.replace(" (leftover)", "")
            recipe = db.execute(
                select(models.Recipe).where(models.Recipe.title == base)
            ).scalar_one_or_none()
            if recipe is None:
                raise HTTPException(status_code=404, detail=f"Recipe '{base}' not found")
            items.append({"id": recipe.id, "title": title})
        result[day] = items
    return result


@app.get("/data/export")
def export_data_endpoint(db: Session = Depends(get_db)) -> Response:
    data = crud.export_data(db)
    return Response(content=data, media_type="application/json")


@app.post("/data/import")
def import_data_endpoint(
    payload: Dict[str, Any],
    mode: str = "overwrite",
    db: Session = Depends(get_db),
) -> Dict[str, str]:
    try:
        crud.import_data(io.StringIO(json.dumps(payload)), db, mode=mode)
    except ValueError as exc:  # pragma: no cover - value error path
        raise HTTPException(status_code=400, detail=str(exc))
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000)
