"""FastAPI application for Meals Planner Codex."""
from __future__ import annotations

import io
import json
import os
import random
from datetime import date
from typing import Annotated, Any, Dict, List, Optional

from fastapi import Depends, FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, Response
from sqlalchemy import select, func
from sqlalchemy.orm import Session, selectinload

import crud
import models
import schemas
import storage
from mealplanner import planner
from mealplanner.seed import seed_system_ingredients, seed_system_tags
from database import SessionLocal, engine, get_db
from scoping import scope
import auth_users

# Ensure database tables exist on startup
models.Base.metadata.create_all(bind=engine)

# Backfill the curated system tags for accounts that predate per-user tagging.
# New accounts get their own set at registration (see ``_create_account``), so
# this only has work to do for pre-existing users and is a no-op once they are
# all caught up.
with SessionLocal() as _session:
    _seeded = set(
        _session.execute(
            select(models.Tag.user_id).where(models.Tag.is_system.is_(True)).distinct()
        ).scalars()
    )
    for _user_id in _session.execute(select(models.User.id)).scalars():
        if _user_id not in _seeded:
            seed_system_tags(_session, _user_id)

app = FastAPI()

# The single authentication mechanism: every route that touches user-owned data
# declares this, and scopes its queries to ``current_user.id``.
CurrentUser = Annotated[models.User, Depends(auth_users.get_current_user)]
Db = Annotated[Session, Depends(get_db)]

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


@app.post("/auth/register", response_model=schemas.UserOut, status_code=201)
def register(
    payload: schemas.UserCreate, db: Db
) -> models.User:
    if crud.get_user_by_email(db, payload.email) is not None:
        raise HTTPException(status_code=400, detail="Email already registered")
    return _create_account(
        db,
        email=payload.email,
        hashed_password=auth_users.hash_password(payload.password),
        display_name=payload.display_name,
    )


def _create_account(
    db: Session,
    *,
    email: str,
    hashed_password: str | None = None,
    display_name: str | None = None,
    auth_provider: str = "local",
    google_sub: str | None = None,
) -> models.User:
    """Create a user and give it the starter data a fresh account needs.

    New accounts start with their own copy of the curated system tags and the
    starter ingredient library, so tagging and recipe entry work out of the box
    without leaking another user's data.
    """
    user = crud.create_user(
        db,
        email=email,
        hashed_password=hashed_password,
        display_name=display_name,
        auth_provider=auth_provider,
        google_sub=google_sub,
    )
    seed_system_tags(db, user.id)
    seed_system_ingredients(db, user.id)
    return user


@app.post("/auth/login", response_model=schemas.Token)
def login(payload: schemas.LoginRequest, db: Db) -> schemas.Token:
    user = crud.get_user_by_email(db, payload.email)
    if (
        user is None
        or user.hashed_password is None
        or not auth_users.verify_password(payload.password, user.hashed_password)
    ):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = auth_users.create_access_token(subject=str(user.id))
    return schemas.Token(access_token=token)


@app.post("/auth/google", response_model=schemas.Token)
def login_with_google(
    payload: schemas.GoogleLoginRequest, db: Db
) -> schemas.Token:
    """Exchange a Google ID token for one of our JWTs, creating the account if new."""
    try:
        claims = auth_users.verify_google_token(payload.credential)
    except ValueError as exc:
        raise HTTPException(
            status_code=401, detail=f"Invalid Google credential: {exc}"
        )

    google_sub = claims["sub"]
    email = claims["email"]
    user = crud.get_user_by_google_sub(db, google_sub) or crud.get_user_by_email(
        db, email
    )
    if user is None:
        user = _create_account(
            db,
            email=email,
            display_name=claims.get("name"),
            auth_provider="google",
            google_sub=google_sub,
        )
    elif user.google_sub is None:
        # Claiming an existing account by email is only safe once Google has
        # verified the address; otherwise anyone could sign up at Google with
        # someone else's email and inherit their account.
        if not claims.get("email_verified"):
            raise HTTPException(
                status_code=401, detail="Google email is not verified"
            )
        user.google_sub = google_sub
        db.commit()
    token = auth_users.create_access_token(subject=str(user.id))
    return schemas.Token(access_token=token)


@app.get("/auth/me", response_model=schemas.UserOut)
def read_me(
    current_user: CurrentUser,
) -> models.User:
    return current_user


@app.put("/auth/me/default-people", response_model=schemas.UserOut)
def set_default_people(
    payload: schemas.DefaultPeopleIn,
    db: Db,
    current_user: CurrentUser,
) -> models.User:
    """Set the user's default people count and apply it to the given range.

    Overwrites ``Meal.people`` for every meal in ``[start_date, end_date]`` and
    stores ``people`` as the default for future meals.
    """
    crud.set_default_people(
        db,
        payload.people,
        payload.start_date,
        payload.end_date,
        current_user.id,
    )
    db.refresh(current_user)
    return current_user


@app.get("/recipes", response_model=List[schemas.RecipeOut])
def read_recipes(
    db: Db,
    current_user: CurrentUser,
) -> List[schemas.RecipeOut]:
    stmt = scope(
        select(models.Recipe).options(
            selectinload(models.Recipe.tags),
            # RecipeOut exposes favorite_side_ids, so without this the
            # serialiser lazy-loads the pairing once per recipe.
            selectinload(models.Recipe.favorite_sides),
            selectinload(models.Recipe.ingredients).selectinload(
                models.RecipeIngredient.ingredient
            ),
        ),
        models.Recipe.user_id,
        current_user.id,
    )
    return db.execute(stmt).scalars().all()


@app.get("/recipes/{recipe_id}", response_model=schemas.RecipeOut)
def read_recipe(
    recipe_id: int,
    db: Db,
    current_user: CurrentUser,
) -> schemas.RecipeOut:
    recipe = crud.get_recipe(db, recipe_id, current_user.id)
    if recipe is None:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return recipe


def _resolve_favorite_sides(
    payload: schemas.RecipeIn, db: Session, user_id: int
) -> List[models.Recipe]:
    """Load the caller's own side recipes named by ``payload.favorite_side_ids``.

    Rejects anything the caller doesn't own or that isn't a side dish, so a
    stale or hand-crafted id can't quietly pair a main with a main. The same
    rule is applied leniently on the import path (``crud.import_data``), which
    drops bad pairings rather than failing a whole file.
    """
    side_ids = list(dict.fromkeys(payload.favorite_side_ids))  # dedupe, keep order
    if not side_ids:
        return []
    if not models.takes_favorite_sides(payload.course):
        raise HTTPException(
            status_code=400,
            detail=f"A {payload.course!r} recipe is not served with a side dish",
        )
    stmt = scope(
        select(models.Recipe).where(models.Recipe.id.in_(side_ids)),
        models.Recipe.user_id,
        user_id,
    )
    found = {r.id: r for r in db.execute(stmt).scalars()}
    resolved: List[models.Recipe] = []
    for side_id in side_ids:
        side = found.get(side_id)
        if side is None:
            raise HTTPException(
                status_code=400, detail=f"Unknown favorite side: {side_id}"
            )
        if not models.is_side_dish(side):
            raise HTTPException(
                status_code=400,
                detail=f"Recipe {side.title!r} is not a side dish",
            )
        resolved.append(side)
    return resolved


def _payload_to_data(payload: schemas.RecipeIn, db: Session, user_id: int) -> dict:
    tags = [crud.get_or_create_tag(db, name, user_id) for name in payload.tags]
    ingredients: List[models.RecipeIngredient] = []
    for ing in payload.ingredients:
        if ing.id is None and not ing.name:
            continue
        ingredient_obj = crud.get_or_create_ingredient(
            db, ing.id, ing.name, ing.unit, user_id
        )
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
        "favorite_sides": _resolve_favorite_sides(payload, db, user_id),
    }


@app.post(
    "/recipes",
    response_model=schemas.RecipeOut,
    status_code=201,
)
def create_recipe(
    payload: schemas.RecipeIn,
    db: Db,
    current_user: CurrentUser,
) -> schemas.RecipeOut:
    data = _payload_to_data(payload, db, current_user.id)
    return crud.create_recipe(db, user_id=current_user.id, **data)


_MAX_IMAGE_BYTES = 5 * 1024 * 1024


@app.post("/recipes/upload-image", status_code=201)
async def upload_recipe_image(
    request: Request,
    current_user: CurrentUser,
    file: UploadFile = File(...),
) -> dict:
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
)
def update_recipe(
    recipe_id: int,
    payload: schemas.RecipeIn,
    db: Db,
    current_user: CurrentUser,
) -> schemas.RecipeOut:
    data = _payload_to_data(payload, db, current_user.id)
    recipe = crud.update_recipe(db, recipe_id, current_user.id, **data)
    if recipe is None:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return recipe


@app.delete(
    "/recipes/{recipe_id}",
    status_code=204,
)
def delete_recipe(
    recipe_id: int,
    db: Db,
    current_user: CurrentUser,
) -> Response:
    deleted = crud.delete_recipe(db, recipe_id, current_user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return Response(status_code=204)


@app.get("/tags", response_model=List[schemas.TagOut])
def read_tags(
    db: Db,
    current_user: CurrentUser,
) -> List[schemas.TagOut]:
    stmt = scope(select(models.Tag), models.Tag.user_id, current_user.id)
    return db.execute(stmt).scalars().all()


def _ingredient_recipe_count(db: Session, ingredient_id: int) -> int:
    return db.scalar(
        select(func.count(models.RecipeIngredient.recipe_id)).where(
            models.RecipeIngredient.ingredient_id == ingredient_id
        )
    ) or 0


@app.get("/ingredients", response_model=List[schemas.IngredientSummary])
def search_ingredients(
    db: Db,
    current_user: CurrentUser,
    search: str = "",
) -> List[schemas.IngredientSummary]:
    stmt = scope(
        select(
            models.Ingredient,
            func.count(models.RecipeIngredient.recipe_id).label("recipe_count"),
        )
        .outerjoin(models.Ingredient.recipes)
        .group_by(models.Ingredient.id)
        .order_by(models.Ingredient.name),
        models.Ingredient.user_id,
        current_user.id,
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
    db: Db,
    current_user: CurrentUser,
    exclude_id: int | None = None,
    threshold: float = 0.8,
) -> List[schemas.IngredientSummary]:
    matches = crud.find_similar_ingredients(
        db, name, exclude_id=exclude_id, threshold=threshold, user_id=current_user.id
    )
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
    db: Db,
    current_user: CurrentUser,
    threshold: float = 0.8,
) -> List[schemas.DuplicatePair]:
    pairs = crud.find_duplicate_pairs(
        db, threshold=threshold, user_id=current_user.id
    )

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
)
def merge_ingredients_endpoint(
    payload: schemas.IngredientMergeRequest,
    db: Db,
    current_user: CurrentUser,
) -> schemas.IngredientSummary:
    try:
        merged = crud.merge_ingredients(
            db,
            payload.source_id,
            payload.target_id,
            surviving_unit=payload.surviving_unit,
            conversion_factor=payload.conversion_factor,
            user_id=current_user.id,
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
)
def create_ingredient(
    payload: schemas.IngredientCreate,
    db: Db,
    current_user: CurrentUser,
) -> schemas.IngredientSummary:
    ingredient = crud.create_ingredient(
        db,
        payload.name,
        payload.unit,
        payload.season_months,
        payload.categories,
        user_id=current_user.id,
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
)
def update_ingredient(
    ingredient_id: int,
    payload: schemas.IngredientUpdate,
    db: Db,
    current_user: CurrentUser,
) -> schemas.IngredientSummary:
    ingredient = crud.get_ingredient(db, ingredient_id, current_user.id)
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
    ingredient_id: int,
    db: Db,
    current_user: CurrentUser,
) -> List[schemas.RecipeSummary]:
    ingredient = crud.get_ingredient(db, ingredient_id, current_user.id)
    if ingredient is None:
        raise HTTPException(status_code=404, detail="Ingredient not found")
    recipes = crud.get_recipes_by_ingredient(db, ingredient_id, current_user.id)
    return [schemas.RecipeSummary(id=r.id, title=r.title) for r in recipes]


@app.delete(
    "/ingredients/{ingredient_id}",
    status_code=204,
)
def delete_ingredient(
    ingredient_id: int,
    db: Db,
    current_user: CurrentUser,
    force: bool = False,
) -> Response:
    deleted = crud.delete_ingredient(
        db, ingredient_id, force=force, user_id=current_user.id
    )
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
    db: Db,
    current_user: CurrentUser,
    plan_date: date | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> Dict[str, List[schemas.MealOut]]:
    return crud.get_plan(db, plan_date, start_date, end_date, current_user.id)


@app.post(
    "/plan",
    response_model=Dict[str, List[schemas.MealOut]],
)
@app.post(
    "/meal-plans",
    response_model=Dict[str, List[schemas.MealOut]],
)
def set_plan(
    payload: schemas.MealPlanCreate,
    db: Db,
    current_user: CurrentUser,
    force: bool = False,
) -> Dict[str, List[schemas.MealOut]]:
    plan_dates = [
        day if isinstance(day, date) else date.fromisoformat(day)
        for day in payload.plan.keys()
    ]
    stmt = scope(
        select(models.MealPlan.plan_date).where(
            models.MealPlan.plan_date.in_(plan_dates)
        ),
        models.MealPlan.user_id,
        current_user.id,
    )
    existing = db.execute(stmt).scalars().all()
    if existing and not force:
        conflicts = [d.isoformat() for d in existing]
        from fastapi.responses import JSONResponse

        return JSONResponse(status_code=409, content={"conflicts": conflicts})

    crud.set_meal_plan(db, payload.plan, current_user.id)
    return crud.get_plan(db, payload.plan_date, user_id=current_user.id)


@app.delete(
    "/plan",
    response_model=Dict[str, int],
)
@app.delete(
    "/meal-plans",
    response_model=Dict[str, int],
)
def delete_meal_plans(
    db: Db,
    current_user: CurrentUser,
    start_date: date = Query(..., description="Inclusive start date for deletion"),
    end_date: date = Query(..., description="Inclusive end date for deletion"),
) -> Dict[str, int]:
    if end_date < start_date:
        raise HTTPException(
            status_code=422, detail="end_date must not be before start_date"
        )

    deleted = crud.delete_meal_plans(db, start_date, end_date, current_user.id)
    return {"deleted": deleted}


@app.get("/plan/settings", response_model=Dict[str, Any])
def plan_settings(
    db: Db,
    current_user: CurrentUser,
) -> Dict[str, Any]:
    """Return the caller's plan settings (defaults + their stored overrides)."""

    return crud.get_plan_settings(db, current_user.id)


@app.put("/plan/settings", response_model=Dict[str, Any])
def update_plan_settings(
    payload: Dict[str, Any],
    db: Db,
    current_user: CurrentUser,
) -> Dict[str, Any]:
    """Persist the caller's plan-setting overrides and return the merged view."""

    return crud.set_plan_settings(db, current_user.id, payload)


@app.post(
    "/meal-plans/accept",
    response_model=schemas.MealOut,
)
def toggle_meal_acceptance(
    payload: schemas.MealAcceptanceIn,
    db: Db,
    current_user: CurrentUser,
) -> schemas.MealOut:
    meal = crud.mark_meal_accepted(
        db, payload.plan_date, payload.meal_number, payload.accepted,
        current_user.id,
    )
    if meal is None or meal.recipe is None:
        raise HTTPException(status_code=404, detail="Meal not found")
    return schemas.MealOut(**crud.meal_item(meal))


@app.post(
    "/meal-plans/people",
    response_model=schemas.MealOut,
)
def set_meal_people(
    payload: schemas.MealPeopleIn,
    db: Db,
    current_user: CurrentUser,
) -> schemas.MealOut:
    meal = crud.set_meal_people(
        db, payload.plan_date, payload.meal_number, payload.people,
        current_user.id,
    )
    if meal is None or meal.recipe is None:
        raise HTTPException(status_code=404, detail="Meal not found")
    return schemas.MealOut(**crud.meal_item(meal))


@app.post("/meal-plans/swap")
def swap_meals(
    payload: schemas.MealSwapIn,
    db: Db,
    current_user: CurrentUser,
) -> dict:
    result = crud.swap_meals(
        db,
        (payload.a.plan_date, payload.a.meal_number),
        (payload.b.plan_date, payload.b.meal_number),
        current_user.id,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Meal not found")
    return {"ok": True}


@app.post(
    "/meal-plans/side",
    response_model=schemas.MealOut,
)
def upsert_side_dish(
    payload: schemas.MealSideIn,
    db: Db,
    current_user: CurrentUser,
) -> schemas.MealOut:
    if payload.index is None:
        meal = crud.add_meal_side(
            db, payload.plan_date, payload.meal_number, payload.side_id,
            current_user.id,
        )
    else:
        meal = crud.replace_meal_side(
            db, payload.plan_date, payload.meal_number, payload.index,
            payload.side_id, current_user.id,
        )
    if meal is None or meal.recipe is None:
        raise HTTPException(status_code=404, detail="Meal not found")
    return schemas.MealOut(**crud.meal_item(meal))


@app.delete(
    "/meal-plans/side",
    response_model=schemas.MealOut,
)
def delete_side_dish(
    payload: schemas.MealSideRemoveIn,
    db: Db,
    current_user: CurrentUser,
) -> schemas.MealOut:
    meal = crud.remove_meal_side(
        db, payload.plan_date, payload.meal_number, payload.index, current_user.id
    )
    if meal is None or meal.recipe is None:
        raise HTTPException(status_code=404, detail="Meal not found")
    return schemas.MealOut(**crud.meal_item(meal))


@app.post("/feedback/accept")
def feedback_accept(
    payload: schemas.FeedbackIn,
    db: Db,
    current_user: CurrentUser,
) -> Dict[str, str]:
    """Record user acceptance of a recipe."""

    if crud.accept_recipe(
        db, payload.title, payload.consumed_date, current_user.id
    ) is None:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return {"status": "ok"}


@app.post("/feedback/reject")
def feedback_reject(
    payload: schemas.FeedbackIn,
    db: Db,
    current_user: CurrentUser,
) -> Dict[str, Optional[str]]:
    """Record user rejection of a recipe and suggest a replacement."""

    if crud.reject_recipe(db, payload.title, current_user.id) is None:
        raise HTTPException(status_code=404, detail="Recipe not found")
    existing = set(crud.list_planned_titles(db, current_user.id))
    existing.add(payload.title)
    available = list(
        set(
            crud.list_recipe_titles(
                db, courses=["main", "first-course"], user_id=current_user.id
            )
        )
        - existing
    )
    replacement = random.choice(available) if available else None
    return {"replacement": replacement}


@app.post("/meal-plans/generate")
def generate_plan_endpoint(
    payload: schemas.MealPlanGenerate,
    db: Db,
    current_user: CurrentUser,
) -> Dict[str, List[Dict[str, object]]]:
    days = (payload.end - payload.start).days + 1
    settings = crud.get_plan_settings(db, current_user.id)
    # The tag-penalty weight is a per-user profile setting, not a per-plan knob,
    # so it comes from the stored settings; the request field is only a fallback.
    tag_penalty_weight = settings.get(
        "tag_penalty_weight", payload.tag_penalty_weight
    )
    slots = planner.generate_plan(
        db,
        user_id=current_user.id,
        plan_settings=settings,
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
        tag_penalty_weight=tag_penalty_weight,
        bulk_bonus_weight=payload.bulk_bonus_weight,
        return_slots=True,
    )
    result: Dict[str, List[Dict[str, object]]] = {}
    for slot in slots:
        recipe = slot.recipe
        if recipe is None:
            raise HTTPException(status_code=404, detail="Recipe not found")
        result.setdefault(slot.date.isoformat(), []).append(
            {
                "id": recipe.id,
                "title": recipe.title,
                "leftover": slot.leftover,
                "side_ids": slot.side_ids,
            }
        )
    return result


@app.post("/side-dishes/generate")
def generate_side_dish_endpoint(
    payload: schemas.SideDishGenerate,
    db: Db,
    current_user: CurrentUser,
) -> Dict[str, object]:
    try:
        recipe = planner.generate_side_dish(
            db,
            user_id=current_user.id,
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
def export_data_endpoint(
    db: Db,
    current_user: CurrentUser,
) -> Response:
    data = crud.export_data(db, current_user.id)
    return Response(content=data, media_type="application/json")


@app.post("/data/import")
def import_data_endpoint(
    payload: Dict[str, Any],
    db: Db,
    current_user: CurrentUser,
    mode: str = "overwrite",
) -> Dict[str, str]:
    try:
        crud.import_data(
            io.StringIO(json.dumps(payload)), db, mode=mode, user_id=current_user.id
        )
    except ValueError as exc:  # pragma: no cover - value error path
        raise HTTPException(status_code=400, detail=str(exc))
    return {"status": "ok"}


@app.delete("/data")
def clear_data_endpoint(
    db: Db,
    current_user: CurrentUser,
) -> Dict[str, str]:
    crud.clear_data(db, current_user.id)
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000)
