"""Pydantic schemas for API responses and requests."""
from __future__ import annotations

from datetime import date
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from models import CATEGORIES, UnitEnum


def _validate_categories(value: List[str]) -> List[str]:
    """Reject any category not in the canonical :data:`models.CATEGORIES`."""

    for item in value:
        if item not in CATEGORIES:
            raise ValueError(f"Unknown category: {item!r}")
    return value


class UserCreate(BaseModel):
    email: str
    password: str
    display_name: Optional[str] = None


class UserOut(BaseModel):
    id: int
    email: str
    display_name: Optional[str] = None
    auth_provider: str
    default_people: int

    model_config = ConfigDict(from_attributes=True)


class LoginRequest(BaseModel):
    email: str
    password: str


class GoogleLoginRequest(BaseModel):
    """The ID token issued by Google Identity Services on the client."""

    credential: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TagOut(BaseModel):
    id: int
    name: str
    penalize_repetition: bool = False
    is_system: bool = False

    model_config = ConfigDict(from_attributes=True)


class IngredientOut(BaseModel):
    id: int
    name: str
    quantity: Optional[float] = None
    unit: Optional[UnitEnum] = None
    season_months: List[int] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


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
    categories: List[str] = Field(default_factory=list)

    _check_categories = field_validator("categories")(_validate_categories)


class IngredientSummary(BaseModel):
    id: int
    name: str
    season_months: List[int] = Field(default_factory=list)
    unit: Optional[UnitEnum] = None
    categories: List[str] = Field(default_factory=list)
    recipe_count: int

    model_config = ConfigDict(from_attributes=True)

    _check_categories = field_validator("categories")(_validate_categories)


class IngredientUpdate(BaseModel):
    name: str
    season_months: List[int] = Field(default_factory=list)
    unit: Optional[UnitEnum] = None
    categories: List[str] = Field(default_factory=list)

    _check_categories = field_validator("categories")(_validate_categories)


class DuplicatePair(BaseModel):
    a: IngredientSummary
    b: IngredientSummary
    score: float


class IngredientMergeRequest(BaseModel):
    source_id: int
    target_id: int
    surviving_unit: Optional[UnitEnum] = None
    conversion_factor: Optional[float] = None


class RecipeSummary(BaseModel):
    id: int
    title: str

    model_config = ConfigDict(from_attributes=True)


class RecipeIn(BaseModel):
    title: str
    servings_default: int
    procedure: Optional[str] = None
    bulk_prep: bool = False
    course: str = "main"
    image_url: Optional[str] = None
    tags: List[str] = []
    ingredients: List[IngredientIn] = []
    # Sides this main is habitually served with; the planner attaches one of
    # them automatically. Only meaningful for main / first-course recipes.
    favorite_side_ids: List[int] = []


class RecipeOut(BaseModel):
    id: int
    title: str
    servings_default: int
    procedure: Optional[str] = None
    bulk_prep: bool
    course: str
    image_url: Optional[str] = None
    score: Optional[float] = None
    date_last_consumed: Optional[date] = None
    ingredients: List[IngredientOut] = []
    tags: List[TagOut] = []
    # Read off ``Recipe.favorite_side_ids``, which flattens the relationship.
    favorite_side_ids: List[int] = []

    model_config = ConfigDict(from_attributes=True)


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
    meal_number: int
    people: int


class MealAcceptanceIn(BaseModel):
    """Payload for toggling a meal's acceptance status."""

    plan_date: date
    meal_number: int
    accepted: bool


class MealPeopleIn(BaseModel):
    """Payload for setting how many people a single meal is cooked for."""

    plan_date: date
    meal_number: int
    people: int = Field(ge=1)


class DefaultPeopleIn(BaseModel):
    """Payload for setting the user's default people count over a date range."""

    people: int = Field(ge=1)
    start_date: date
    end_date: date


class MealPosition(BaseModel):
    """A single meal slot addressed by date and meal number."""

    plan_date: date
    meal_number: int


class MealSwapIn(BaseModel):
    """Payload for swapping two meals' positions."""

    a: MealPosition
    b: MealPosition


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
