"""Pydantic schemas for API responses and requests."""
from __future__ import annotations

from datetime import date
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, root_validator

from models import UnitEnum


class TagOut(BaseModel):
    id: int
    name: str

    class Config:
        orm_mode = True


class IngredientBase(BaseModel):
    id: Optional[int] = None
    name: str
    unit: Optional[UnitEnum] = None
    season_months: List[int] = Field(default_factory=list)

    class Config:
        orm_mode = True


class RecipeIngredientIn(BaseModel):
    quantity: Optional[float] = None
    ingredient: IngredientBase


class RecipeIngredientOut(BaseModel):
    quantity: Optional[float] = None
    ingredient: IngredientBase

    @root_validator(pre=True)
    def nest_ingredient(cls, values: object) -> Dict[str, object]:
        if not isinstance(values, dict):
            obj = values
            values = {
                "quantity": getattr(obj, "quantity", None),
                "ingredient": {
                    "id": getattr(obj, "id", None),
                    "name": getattr(obj, "name", None),
                    "unit": getattr(obj, "unit", None),
                    "season_months": getattr(obj, "season_months", []),
                },
            }
            return values
        if "ingredient" not in values:
            keys = {"id", "name", "unit", "season_months"}
            ing_data = {k: values.pop(k) for k in list(values.keys()) if k in keys}
            values["ingredient"] = ing_data
        return values

    class Config:
        orm_mode = True


class RecipeIn(BaseModel):
    title: str
    servings_default: int
    procedure: Optional[str] = None
    bulk_prep: bool = False
    tags: List[str] = []
    ingredients: List[RecipeIngredientIn] = []


class RecipeOut(BaseModel):
    id: int
    title: str
    servings_default: int
    procedure: Optional[str] = None
    bulk_prep: bool
    score: Optional[float] = None
    date_last_consumed: Optional[date] = None
    ingredients: List[RecipeIngredientOut] = []
    tags: List[TagOut] = []

    class Config:
        orm_mode = True


class MealPlanCreate(BaseModel):
    plan_date: date
    plan: Dict[str, List[int]]
    bulk_leftovers: bool | None = None
    keep_days: int | None = None


class MealPlanGenerate(BaseModel):
    start: date
    days: int
    meals_per_day: int
    epsilon: float = 0.0
    avoid_tags: List[str] = []
    reduce_tags: List[str] = []
    seasonality_weight: float = 1.0
    recency_weight: float = 1.0
    tag_penalty_weight: float = 1.0
    bulk_bonus_weight: float = 1.0
    bulk_leftovers: bool = True
    keep_days: int = 7


class FeedbackIn(BaseModel):
    """Payload for feedback endpoints."""

    title: str
