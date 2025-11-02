"""Pydantic schemas for API responses and requests."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, EmailStr, Field, root_validator

from models import UnitEnum


class UserBase(BaseModel):
    """Shared attributes for user-facing schemas."""

    email: EmailStr
    username: str


class UserCreate(UserBase):
    """Payload for user creation."""

    password: str


class UserLogin(BaseModel):
    """Authentication payload accepting an email or username."""

    email: EmailStr | None = None
    username: str | None = None
    password: str

    @root_validator(skip_on_failure=True)
    def _validate_identifier(cls, values: Dict[str, Optional[str]]) -> Dict[str, Optional[str]]:
        if not values.get("email") and not values.get("username"):
            raise ValueError("Either email or username must be provided")
        return values


class UserOut(UserBase):
    """Representation of a user without sensitive fields."""

    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True
        from_attributes = True


class Token(BaseModel):
    """Bearer token returned after successful authentication."""

    access_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    """Data encoded in authentication tokens."""

    sub: str | None = None
    exp: int | None = None


class OwnedModel(BaseModel):
    """Base schema for resources owned by a user."""

    user_id: int

    @root_validator(pre=True)
    def _populate_user_id(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        if isinstance(values, dict):
            owner_id = values.get("owner_id")
            if values.get("user_id") is None and owner_id is not None:
                values["user_id"] = owner_id
            return values

        user_id = getattr(values, "user_id", None)
        if user_id is None and hasattr(values, "owner_id"):
            setattr(values, "user_id", getattr(values, "owner_id"))
        return values

    class Config:
        orm_mode = True
        from_attributes = True


class TagOut(OwnedModel):
    id: int
    name: str


class IngredientOut(OwnedModel):
    id: int
    name: str
    quantity: Optional[float] = None
    unit: Optional[UnitEnum] = None
    season_months: List[int] = Field(default_factory=list)


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


class IngredientSummary(OwnedModel):
    id: int
    name: str
    season_months: List[int] = Field(default_factory=list)
    unit: Optional[UnitEnum] = None
    recipe_count: int


class IngredientUpdate(BaseModel):
    name: str
    season_months: List[int] = Field(default_factory=list)
    unit: Optional[UnitEnum] = None


class RecipeSummary(OwnedModel):
    id: int
    title: str


class RecipeIn(BaseModel):
    title: str
    servings_default: int
    procedure: Optional[str] = None
    bulk_prep: bool = False
    course: str = "main"
    tags: List[str] = []
    ingredients: List[IngredientIn] = []


class RecipeOut(OwnedModel):
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


class MealAssignment(BaseModel):
    main_id: int
    side_ids: List[int] = Field(default_factory=list)
    leftover: bool = False


class MealPlanCreate(BaseModel):
    plan_date: date
    plan: Dict[str, List[MealAssignment]]
    bulk_leftovers: bool | None = None
    keep_days: int | None = None


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
