"""Pydantic schemas for API responses and requests."""
from __future__ import annotations

from datetime import date
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, model_validator

from models import UnitEnum


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


class IngredientCreate(BaseModel):
    name: str
    season_months: List[int] = Field(default_factory=list)
    unit: Optional[UnitEnum] = None


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


class RecipeSummary(BaseModel):
    id: int
    title: str

    class Config:
        orm_mode = True


class RecipeIn(BaseModel):
    title: str
    servings_default: int
    procedure: Optional[str] = None
    bulk_prep: bool = False
    course: str = "main"
    tags: List[str] = []
    ingredients: List[IngredientIn] = []


class RecipeOut(BaseModel):
    id: int
    title: str
    servings_default: int
    procedure: Optional[str] = None
    bulk_prep: bool
    course: str
    score: Optional[float] = None
    date_last_consumed: Optional[date] = None
    ingredients: List[IngredientOut] = []
    tags: List[TagOut] = []

    class Config:
        orm_mode = True


class MealAssignment(BaseModel):
    main_id: int
    side_ids: List[int] = Field(default_factory=list)
    leftover: bool = False


class MealPlanCreate(BaseModel):
    plan_date: date
    plan: Dict[str, List[MealAssignment]]
    bulk_leftovers: bool | None = None
    keep_days: int | None = None


class MealPlanDelete(BaseModel):
    """Payload for deleting meal plans within a date range."""

    start_date: date
    end_date: date


class MealPlanGenerate(BaseModel):
    start: date
    end: date
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
    leftover_repeat_default: int | None = None
    leftover_repeat_by_recipe: Dict[int, int] | None = None
    leftover_spacing_gap: int | None = None
    max_leftovers_per_day: int | None = None
    max_leftovers_per_week: int | None = None
    leftover_accept_weight: float | None = None
    leftover_daypart_pref: Dict[str, float] | None = None
    leftover_daypart_weight: float | None = None
    protect_explore_slots: bool | None = None
    soft_hold_penalty: float | None = None
    explore_protection_cost: float | None = None
    meal_number_to_daypart: Dict[int, str] | None = None

    @model_validator(mode="after")
    def _validate_range(self):
        if self.end < self.start:
            raise ValueError("end must be on or after start")
        return self

    @property
    def days(self) -> int:
        """Inclusive number of days in the requested plan."""

        return (self.end - self.start).days + 1


class SideDishGenerate(BaseModel):
    """Parameters for generating a side dish recommendation."""

    epsilon: float = 0.0
    avoid_titles: List[str] = []
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
    consumed_date: date


class MealOut(BaseModel):
    """Represents a meal within a plan."""

    recipe: str
    side_recipes: List[str] = Field(default_factory=list)
    accepted: bool
    leftover: bool = False


class MealAcceptanceIn(BaseModel):
    """Payload for toggling a meal's acceptance status."""

    plan_date: date
    meal_number: int
    accepted: bool


class MealSideIn(BaseModel):
    """Payload for adding or replacing a side dish."""

    plan_date: date
    meal_number: int
    side_id: int
    index: int | None = None


class MealSideRemoveIn(BaseModel):
    """Payload for removing a side dish from a meal."""

    plan_date: date
    meal_number: int
    index: int
