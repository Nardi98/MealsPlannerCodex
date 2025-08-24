"""FastAPI application for Meals Planner Codex."""
from __future__ import annotations

from datetime import date
from typing import Dict, List

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

import crud
import models
import schemas
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
        selectinload(models.Recipe.tags), selectinload(models.Recipe.ingredients)
    )
    return db.execute(stmt).scalars().all()


def _payload_to_data(payload: schemas.RecipeIn, db: Session) -> dict:
    tags = [crud.get_or_create_tag(db, name) for name in payload.tags]
    ingredients = [models.Ingredient(**ing.model_dump()) for ing in payload.ingredients]
    return {
        "title": payload.title,
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


@app.get("/plan", response_model=Dict[str, List[str]])
def get_plan(plan_date: date | None = None, db: Session = Depends(get_db)) -> Dict[str, List[str]]:
    return crud.get_plan(db, plan_date)


@app.post("/plan", response_model=Dict[str, List[str]])
def set_plan(payload: schemas.MealPlanCreate, db: Session = Depends(get_db)) -> Dict[str, List[str]]:
    crud.set_meal_plan(db, payload.plan_date, payload.plan)
    return crud.get_plan(db, payload.plan_date)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000)
