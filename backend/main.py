"""FastAPI application for Meals Planner Codex."""
from __future__ import annotations

from datetime import date
from typing import Dict, List

from fastapi import Depends
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

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
    return db.execute(select(models.Recipe)).scalars().all()


@app.get("/tags", response_model=List[schemas.TagOut])
def read_tags(db: Session = Depends(get_db)) -> List[schemas.TagOut]:
    return db.execute(select(models.Tag)).scalars().all()


@app.get("/ingredients", response_model=List[str])
def read_ingredients(search: str = "", db: Session = Depends(get_db)) -> List[str]:
    stmt = select(models.Ingredient.name).distinct()
    if search:
        stmt = stmt.where(models.Ingredient.name.ilike(f"%{search}%"))
    return db.execute(stmt).scalars().all()


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
