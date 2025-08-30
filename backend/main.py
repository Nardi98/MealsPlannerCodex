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
from sqlalchemy import select, func
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
        selectinload(models.Recipe.ingredients).selectinload(
            models.RecipeIngredient.ingredient
        ),
    )
    return db.execute(stmt).scalars().all()


def _payload_to_data(payload: schemas.RecipeIn, db: Session) -> dict:
    tags = [crud.get_or_create_tag(db, name) for name in payload.tags]
    ingredients: List[models.RecipeIngredient] = []
    for ing in payload.ingredients:
        if ing.id is None and not ing.name:
            continue
        ingredient_obj = crud.get_or_create_ingredient(db, ing.id, ing.name, ing.unit)
        ingredient_obj.season_months = ing.season_months or list(range(1, 13))
        ingredients.append(
            models.RecipeIngredient(
                ingredient=ingredient_obj,
                quantity=ing.quantity,
                unit=ing.unit,
            )
        )
    return {
        "title": payload.title,
        "course": payload.course,
        "servings_default": payload.servings_default,
        "procedure": payload.procedure,
        "bulk_prep": payload.bulk_prep,
        "tags": tags,
        "ingredients": ingredients,
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
def delete_recipe(recipe_id: int, db: Session = Depends(get_db)) -> Response:
    deleted = crud.delete_recipe(db, recipe_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return Response(status_code=204)


@app.get("/tags", response_model=List[schemas.TagOut])
def read_tags(db: Session = Depends(get_db)) -> List[schemas.TagOut]:
    return db.execute(select(models.Tag)).scalars().all()


@app.get("/ingredients", response_model=List[schemas.IngredientSummary])
def search_ingredients(
    search: str = "", db: Session = Depends(get_db)
) -> List[schemas.IngredientSummary]:
    stmt = (
        select(
            models.Ingredient,
            func.count(models.RecipeIngredient.recipe_id).label("recipe_count"),
        )
        .outerjoin(models.Ingredient.recipes)
        .group_by(models.Ingredient.id)
        .order_by(models.Ingredient.name)
    )
    if search:
        stmt = stmt.where(models.Ingredient.name.ilike(f"{search}%")).limit(10)
    rows = db.execute(stmt).all()
    return [
        schemas.IngredientSummary(
            id=ing.id,
            name=ing.name,
            season_months=ing.season_months or [],
            unit=ing.unit,
            recipe_count=count,
        )
        for ing, count in rows
    ]


@app.put("/ingredients/{ingredient_id}", response_model=schemas.IngredientSummary)
def update_ingredient(
    ingredient_id: int,
    payload: schemas.IngredientUpdate,
    db: Session = Depends(get_db),
) -> schemas.IngredientSummary:
    ingredient = db.get(models.Ingredient, ingredient_id)
    if ingredient is None:
        raise HTTPException(status_code=404, detail="Ingredient not found")
    ingredient.name = payload.name
    ingredient.season_months = payload.season_months
    ingredient.unit = payload.unit
    db.commit()
    count = db.scalar(
        select(func.count(models.RecipeIngredient.recipe_id)).where(
            models.RecipeIngredient.ingredient_id == ingredient.id
        )
    )
    return schemas.IngredientSummary(
        id=ingredient.id,
        name=ingredient.name,
        season_months=ingredient.season_months or [],
        unit=ingredient.unit,
        recipe_count=count or 0,
    )


@app.get("/plan", response_model=Dict[str, List[schemas.MealOut]])
@app.get("/meal-plans", response_model=Dict[str, List[schemas.MealOut]])
def get_plan(
    plan_date: date | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    db: Session = Depends(get_db),
) -> Dict[str, List[schemas.MealOut]]:
    return crud.get_plan(db, plan_date, start_date, end_date)


@app.post("/plan", response_model=Dict[str, List[schemas.MealOut]])
@app.post("/meal-plans", response_model=Dict[str, List[schemas.MealOut]])
def set_plan(
    payload: schemas.MealPlanCreate,
    force: bool = False,
    db: Session = Depends(get_db),
) -> Dict[str, List[schemas.MealOut]]:
    plan_dates = [
        day if isinstance(day, date) else date.fromisoformat(day)
        for day in payload.plan.keys()
    ]
    stmt = select(models.MealPlan.plan_date).where(
        models.MealPlan.plan_date.in_(plan_dates)
    )
    existing = db.execute(stmt).scalars().all()
    if existing and not force:
        conflicts = [d.isoformat() for d in existing]
        from fastapi.responses import JSONResponse

        return JSONResponse(status_code=409, content={"conflicts": conflicts})

    crud.set_meal_plan(db, payload.plan)
    title_plan: Dict[str, List[Dict[str, object]]] = {}
    for day, meals in payload.plan.items():
        titles: List[Dict[str, object]] = []
        for item in meals:
            recipe = db.get(models.Recipe, item.main_id)
            side_titles: List[str] = []
            for sid in getattr(item, "side_ids", []) or []:
                sr = db.get(models.Recipe, sid)
                if sr is not None:
                    side_titles.append(sr.title)
            if recipe is not None:
                titles.append(
                    {
                        "recipe": recipe.title,
                        "side_recipes": side_titles,
                        "accepted": False,
                    }
                )
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


@app.post("/meal-plans/accept", response_model=schemas.MealOut)
def toggle_meal_acceptance(
    payload: schemas.MealAcceptanceIn, db: Session = Depends(get_db)
) -> schemas.MealOut:
    meal = crud.mark_meal_accepted(
        db, payload.plan_date, payload.meal_number, payload.accepted
    )
    if meal is None or meal.recipe is None:
        raise HTTPException(status_code=404, detail="Meal not found")
    return schemas.MealOut(
        recipe=meal.recipe.title,
        side_recipes=[ms.side_recipe.title for ms in meal.sides if ms.side_recipe],
        accepted=meal.accepted,
    )


@app.post("/meal-plans/side", response_model=schemas.MealOut)
def upsert_side_dish(
    payload: schemas.MealSideIn, db: Session = Depends(get_db)
) -> schemas.MealOut:
    if payload.index is None:
        meal = crud.add_meal_side(
            db, payload.plan_date, payload.meal_number, payload.side_id
        )
    else:
        meal = crud.replace_meal_side(
            db, payload.plan_date, payload.meal_number, payload.index, payload.side_id
        )
    if meal is None or meal.recipe is None:
        raise HTTPException(status_code=404, detail="Meal not found")
    return schemas.MealOut(
        recipe=meal.recipe.title,
        side_recipes=[ms.side_recipe.title for ms in meal.sides if ms.side_recipe],
        accepted=meal.accepted,
    )


@app.delete("/meal-plans/side", response_model=schemas.MealOut)
def delete_side_dish(
    payload: schemas.MealSideRemoveIn, db: Session = Depends(get_db)
) -> schemas.MealOut:
    meal = crud.remove_meal_side(
        db, payload.plan_date, payload.meal_number, payload.index
    )
    if meal is None or meal.recipe is None:
        raise HTTPException(status_code=404, detail="Meal not found")
    return schemas.MealOut(
        recipe=meal.recipe.title,
        side_recipes=[ms.side_recipe.title for ms in meal.sides if ms.side_recipe],
        accepted=meal.accepted,
    )


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
        meal["recipe"][:-11] if meal["recipe"].endswith(" (leftover)") else meal["recipe"]
        for meals in crud.get_plan().values()
        for meal in meals
    }
    existing.add(payload.title)
    available = list(
        set(crud.list_recipe_titles(db, courses=["main", "first-course"])) - existing
    )
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
                select(models.Recipe).where(models.Recipe.title == base).limit(1)
            ).scalar_one_or_none()
            if recipe is None:
                raise HTTPException(status_code=404, detail=f"Recipe '{base}' not found")
            items.append({"id": recipe.id, "title": title})
        result[day] = items
    return result


@app.post("/side-dishes/generate")
def generate_side_dish_endpoint(
    payload: schemas.SideDishGenerate, db: Session = Depends(get_db)
) -> Dict[str, object]:
    try:
        recipe = planner.generate_side_dish(
            db,
            avoid_tags=payload.avoid_tags,
            reduce_tags=payload.reduce_tags,
            epsilon=payload.epsilon,
            keep_days=payload.keep_days,
            bulk_leftovers=payload.bulk_leftovers,
            seasonality_weight=payload.seasonality_weight,
            recency_weight=payload.recency_weight,
            tag_penalty_weight=payload.tag_penalty_weight,
            bulk_bonus_weight=payload.bulk_bonus_weight,
        )
    except ValueError as exc:  # pragma: no cover - error path
        raise HTTPException(status_code=400, detail=str(exc))
    return {"id": recipe.id, "title": recipe.title}


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


@app.delete("/data")
def clear_data_endpoint(db: Session = Depends(get_db)) -> Dict[str, str]:
    crud.clear_data(db)
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000)
