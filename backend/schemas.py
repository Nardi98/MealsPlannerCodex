"""Pydantic schemas for API responses and requests."""
from __future__ import annotations

from datetime import date
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from models import UnitEnum, CourseEnum


class TagOut(BaseModel):
    id: int
    name: str

    class Config:
        orm_mode = True


class IngredientOut(BaseModel):
    id: int
    name: str
    quantity: Optional[float] = None
    unit: Optional[UnitEnum] = None
    season_months: List[int] = Field(default_factory=list)

    class Config:
        orm_mode = True


class IngredientIn(BaseModel):
    id: int | None = None
    name: str | None = None
    quantity: Optional[float] = None
    unit: Optional[UnitEnum] = None
    season_months: List[int] = Field(default_factory=list)


class IngredientSummary(BaseModel):
    id: int
    name: str
    season_months: List[int] = Field(default_factory=list)
    unit: Optional[UnitEnum] = None
    recipe_count: int

    class Config:
        orm_mode = True


class IngredientUpdate(BaseModel):
    name: str
    season_months: List[int] = Field(default_factory=list)
    unit: Optional[UnitEnum] = None


class RecipeIn(BaseModel):
    title: str
    servings_default: int
    course: CourseEnum = CourseEnum.MAIN_DISH
    procedure: Optional[str] = None
    bulk_prep: bool = False
    tags: List[str] = []
    ingredients: List[IngredientIn] = []


class RecipeOut(BaseModel):
    id: int
    title: str
    servings_default: int
    course: CourseEnum
    procedure: Optional[str] = None
    bulk_prep: bool
    score: Optional[float] = None
    date_last_consumed: Optional[date] = None
    ingredients: List[IngredientOut] = []
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


class MealOut(BaseModel):
    """Represents a meal within a plan."""

    recipe: str
    course: CourseEnum
    accepted: bool


class MealAcceptanceIn(BaseModel):
    """Payload for toggling a meal's acceptance status."""

    plan_date: date
    meal_number: int
    accepted: bool
