"""FastAPI application for Meals Planner Codex."""
from __future__ import annotations

import io
import json
import os
import random
from datetime import date
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, Response
from sqlalchemy import select, func
from sqlalchemy.orm import Session, selectinload

import crud
import models
import schemas
import storage
from auth import require_api_key
from mealplanner import planner
from mealplanner.seed import seed_system_tags
from database import SessionLocal, engine

# Ensure database tables exist on startup
models.Base.metadata.create_all(bind=engine)

# Seed the curated system tags (with repetition-penalty flags) so tagging a
# recipe with a known format tag transparently reuses the penalized system tag.
with SessionLocal() as _session:
    seed_system_tags(_session)

app = FastAPI()

# Applied to mutating routes so they honour ``API_KEY`` when configured.
_AUTH = [Depends(require_api_key)]

# Restrict CORS to the configured frontend origin(s). ``ALLOWED_ORIGINS`` is a
# comma-separated list; default to the local dev server. Credentials are only
# enabled when concrete origins are set (a wildcard + credentials is rejected by
# browsers and is a security smell).
_allowed_origins = [
    origin.strip()
    for origin in os.environ.get("ALLOWED_ORIGINS", "http://localhost:3000").split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials="*" not in _allowed_origins,
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


@app.get("/recipes/{recipe_id}", response_model=schemas.RecipeOut)
def read_recipe(recipe_id: int, db: Session = Depends(get_db)) -> schemas.RecipeOut:
    recipe = crud.get_recipe(db, recipe_id)
    if recipe is None:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return recipe


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
        "image_url": payload.image_url,
        "tags": tags,
        "ingredients": ingredients,
    }


@app.post(
    "/recipes",
    response_model=schemas.RecipeOut,
    status_code=201,
    dependencies=_AUTH,
)
def create_recipe(payload: schemas.RecipeIn, db: Session = Depends(get_db)) -> schemas.RecipeOut:
    data = _payload_to_data(payload, db)
    return crud.create_recipe(db, **data)


_MAX_IMAGE_BYTES = 5 * 1024 * 1024


@app.post("/recipes/upload-image", status_code=201, dependencies=_AUTH)
async def upload_recipe_image(request: Request, file: UploadFile = File(...)) -> dict:
    """Store an uploaded image and return an absolute URL that serves it back."""
    data = await file.read()
    if len(data) > _MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Image exceeds the 5 MB limit")
    try:
        key = storage.save_image(data, file.content_type or "")
    except ValueError:
        raise HTTPException(status_code=415, detail="Unsupported image type")
    image_url = f"{str(request.base_url).rstrip('/')}/recipes/images/{key}"
    return {"image_url": image_url}


@app.get("/recipes/images/{key:path}")
def serve_recipe_image(key: str) -> Response:
    """Stream a previously uploaded image by its storage key."""
    try:
        data, content_type = storage.open_image(key)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Image not found")
    return Response(content=data, media_type=content_type)


@app.put(
    "/recipes/{recipe_id}",
    response_model=schemas.RecipeOut,
    dependencies=_AUTH,
)
def update_recipe(
    recipe_id: int, payload: schemas.RecipeIn, db: Session = Depends(get_db)
) -> schemas.RecipeOut:
    data = _payload_to_data(payload, db)
    recipe = crud.update_recipe(db, recipe_id, **data)
    if recipe is None:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return recipe


@app.delete(
    "/recipes/{recipe_id}",
    status_code=204,
    dependencies=_AUTH,
)
def delete_recipe(recipe_id: int, db: Session = Depends(get_db)) -> Response:
    deleted = crud.delete_recipe(db, recipe_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return Response(status_code=204)


@app.get("/tags", response_model=List[schemas.TagOut])
def read_tags(db: Session = Depends(get_db)) -> List[schemas.TagOut]:
    return db.execute(select(models.Tag)).scalars().all()


def _ingredient_recipe_count(db: Session, ingredient_id: int) -> int:
    return db.scalar(
        select(func.count(models.RecipeIngredient.recipe_id)).where(
            models.RecipeIngredient.ingredient_id == ingredient_id
        )
    ) or 0


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
            categories=ing.categories or [],
            recipe_count=count,
        )
        for ing, count in rows
    ]


@app.get(
    "/ingredients/similar",
    response_model=List[schemas.IngredientSummary],
)
def similar_ingredients(
    name: str,
    exclude_id: int | None = None,
    db: Session = Depends(get_db),
) -> List[schemas.IngredientSummary]:
    matches = crud.find_similar_ingredients(db, name, exclude_id=exclude_id)
    return [
        schemas.IngredientSummary(
            id=ing.id,
            name=ing.name,
            season_months=ing.season_months or [],
            unit=ing.unit,
            categories=ing.categories or [],
            recipe_count=_ingredient_recipe_count(db, ing.id),
        )
        for ing in matches
    ]


@app.get(
    "/ingredients/duplicates",
    response_model=List[schemas.DuplicatePair],
)
def duplicate_ingredients(
    threshold: float = 0.8, db: Session = Depends(get_db)
) -> List[schemas.DuplicatePair]:
    pairs = crud.find_duplicate_pairs(db, threshold=threshold)

    def summary(ing: models.Ingredient) -> schemas.IngredientSummary:
        return schemas.IngredientSummary(
            id=ing.id,
            name=ing.name,
            season_months=ing.season_months or [],
            unit=ing.unit,
            categories=ing.categories or [],
            recipe_count=_ingredient_recipe_count(db, ing.id),
        )

    return [
        schemas.DuplicatePair(a=summary(a), b=summary(b), score=score)
        for a, b, score in pairs
    ]


@app.post(
    "/ingredients/merge",
    response_model=schemas.IngredientSummary,
    dependencies=_AUTH,
)
def merge_ingredients_endpoint(
    payload: schemas.IngredientMergeRequest, db: Session = Depends(get_db)
) -> schemas.IngredientSummary:
    try:
        merged = crud.merge_ingredients(
            db,
            payload.source_id,
            payload.target_id,
            surviving_unit=payload.surviving_unit,
            conversion_factor=payload.conversion_factor,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if merged is None:
        raise HTTPException(status_code=404, detail="Ingredient not found")
    return schemas.IngredientSummary(
        id=merged.id,
        name=merged.name,
        season_months=merged.season_months or [],
        unit=merged.unit,
        categories=merged.categories or [],
        recipe_count=_ingredient_recipe_count(db, merged.id),
    )


@app.post(
    "/ingredients",
    response_model=schemas.IngredientSummary,
    status_code=201,
    dependencies=_AUTH,
)
def create_ingredient(
    payload: schemas.IngredientCreate, db: Session = Depends(get_db)
) -> schemas.IngredientSummary:
    ingredient = crud.create_ingredient(
        db, payload.name, payload.unit, payload.season_months, payload.categories
    )
    return schemas.IngredientSummary(
        id=ingredient.id,
        name=ingredient.name,
        season_months=ingredient.season_months or [],
        unit=ingredient.unit,
        categories=ingredient.categories or [],
        recipe_count=0,
    )


@app.put(
    "/ingredients/{ingredient_id}",
    response_model=schemas.IngredientSummary,
    dependencies=_AUTH,
)
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
    ingredient.categories = payload.categories
    db.commit()
    return schemas.IngredientSummary(
        id=ingredient.id,
        name=ingredient.name,
        season_months=ingredient.season_months or [],
        unit=ingredient.unit,
        categories=ingredient.categories or [],
        recipe_count=_ingredient_recipe_count(db, ingredient.id),
    )


@app.get(
    "/ingredients/{ingredient_id}/recipes",
    response_model=List[schemas.RecipeSummary],
)
def ingredient_recipes(
    ingredient_id: int, db: Session = Depends(get_db)
) -> List[schemas.RecipeSummary]:
    ingredient = crud.get_ingredient(db, ingredient_id)
    if ingredient is None:
        raise HTTPException(status_code=404, detail="Ingredient not found")
    recipes = crud.get_recipes_by_ingredient(db, ingredient_id)
    return [schemas.RecipeSummary(id=r.id, title=r.title) for r in recipes]


@app.delete(
    "/ingredients/{ingredient_id}",
    status_code=204,
    dependencies=_AUTH,
)
def delete_ingredient(
    ingredient_id: int, force: bool = False, db: Session = Depends(get_db)
) -> Response:
    deleted = crud.delete_ingredient(db, ingredient_id, force=force)
    if deleted is None:
        raise HTTPException(status_code=404, detail="Ingredient not found")
    if deleted is False:
        raise HTTPException(
            status_code=400, detail="Ingredient is referenced by recipes"
        )
    return Response(status_code=204)


# DEPRECATED: the legacy `/plan` routes below are kept for backward
# compatibility only. Prefer the `/meal-plans` paths. Removal is scheduled no
# earlier than 2026-10-01; do not add new behaviour to the `/plan` paths.
@app.get("/plan", response_model=Dict[str, List[schemas.MealOut]])
@app.get("/meal-plans", response_model=Dict[str, List[schemas.MealOut]])
def get_plan(
    plan_date: date | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    db: Session = Depends(get_db),
) -> Dict[str, List[schemas.MealOut]]:
    return crud.get_plan(db, plan_date, start_date, end_date)


@app.post(
    "/plan",
    response_model=Dict[str, List[schemas.MealOut]],
    dependencies=_AUTH,
)
@app.post(
    "/meal-plans",
    response_model=Dict[str, List[schemas.MealOut]],
    dependencies=_AUTH,
)
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
    return crud.get_plan(db, payload.plan_date)


@app.delete(
    "/plan",
    response_model=Dict[str, int],
    dependencies=_AUTH,
)
@app.delete(
    "/meal-plans",
    response_model=Dict[str, int],
    dependencies=_AUTH,
)
def delete_meal_plans(
    start_date: date = Query(..., description="Inclusive start date for deletion"),
    end_date: date = Query(..., description="Inclusive end date for deletion"),
    db: Session = Depends(get_db),
) -> Dict[str, int]:
    if end_date < start_date:
        raise HTTPException(
            status_code=422, detail="end_date must not be before start_date"
        )

    deleted = crud.delete_meal_plans(db, start_date, end_date)
    return {"deleted": deleted}


@app.get("/plan/settings", response_model=Dict[str, Any])
def plan_settings(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Return plan settings (currently the defaults; per-user overrides later)."""

    return crud.get_plan_settings(db)


@app.post(
    "/meal-plans/accept",
    response_model=schemas.MealOut,
    dependencies=_AUTH,
)
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
        leftover=meal.leftover,
    )


@app.post(
    "/meal-plans/side",
    response_model=schemas.MealOut,
    dependencies=_AUTH,
)
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
        leftover=meal.leftover,
    )


@app.delete(
    "/meal-plans/side",
    response_model=schemas.MealOut,
    dependencies=_AUTH,
)
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
        leftover=meal.leftover,
    )


@app.post("/feedback/accept", dependencies=_AUTH)
def feedback_accept(
    payload: schemas.FeedbackIn, db: Session = Depends(get_db)
) -> Dict[str, str]:
    """Record user acceptance of a recipe."""

    if crud.accept_recipe(db, payload.title, payload.consumed_date) is None:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return {"status": "ok"}


@app.post("/feedback/reject", dependencies=_AUTH)
def feedback_reject(
    payload: schemas.FeedbackIn, db: Session = Depends(get_db)
) -> Dict[str, Optional[str]]:
    """Record user rejection of a recipe and suggest a replacement."""

    if crud.reject_recipe(db, payload.title) is None:
        raise HTTPException(status_code=404, detail="Recipe not found")
    existing = set(crud.list_planned_titles(db))
    existing.add(payload.title)
    available = list(
        set(crud.list_recipe_titles(db, courses=["main", "first-course"])) - existing
    )
    replacement = random.choice(available) if available else None
    return {"replacement": replacement}


@app.post("/meal-plans/generate", dependencies=_AUTH)
def generate_plan_endpoint(
    payload: schemas.MealPlanGenerate, db: Session = Depends(get_db)
) -> Dict[str, List[Dict[str, object]]]:
    days = (payload.end - payload.start).days + 1
    slots = planner.generate_plan(
        db,
        start=payload.start,
        days=days,
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
        return_slots=True,
    )
    result: Dict[str, List[Dict[str, object]]] = {}
    for slot in slots:
        recipe = slot.recipe
        if recipe is None:
            raise HTTPException(status_code=404, detail="Recipe not found")
        result.setdefault(slot.date.isoformat(), []).append(
            {"id": recipe.id, "title": recipe.title, "leftover": slot.leftover}
        )
    return result


@app.post("/side-dishes/generate", dependencies=_AUTH)
def generate_side_dish_endpoint(
    payload: schemas.SideDishGenerate, db: Session = Depends(get_db)
) -> Dict[str, object]:
    try:
        recipe = planner.generate_side_dish(
            db,
            avoid_tags=payload.avoid_tags,
            reduce_tags=payload.reduce_tags,
            avoid_titles=payload.avoid_titles,
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


@app.post("/data/import", dependencies=_AUTH)
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


@app.delete("/data", dependencies=_AUTH)
def clear_data_endpoint(db: Session = Depends(get_db)) -> Dict[str, str]:
    crud.clear_data(db)
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000)
