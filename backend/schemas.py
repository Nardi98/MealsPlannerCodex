"""Pydantic schemas for API responses and requests."""
from __future__ import annotations

from datetime import date, datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

import usernames
from models import CATEGORIES, VISIBILITY_VALUES, UnitEnum

#: VIS-5. Stated once, so the schema validator and ``main``'s 400 handler
#: cannot drift apart.
PUBLIC_VISIBILITY_MESSAGE = "Public recipes are not available yet"

# bcrypt truncates anything past 72 bytes, so passwords longer than that are
# rejected rather than silently trimmed.
PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_BYTES = 72


def _validate_categories(value: List[str]) -> List[str]:
    """Reject any category not in the canonical :data:`models.CATEGORIES`."""

    for item in value:
        if item not in CATEGORIES:
            raise ValueError(f"Unknown category: {item!r}")
    return value


def validate_password(pw: str) -> str:
    """Enforce password length (8-72 bytes) and complexity requirements.

    Length is measured in UTF-8 bytes because bcrypt caps input at 72 bytes.
    Complexity requires at least one uppercase, one lowercase, and one digit.
    Returns the password unchanged when valid; raises ``ValueError`` otherwise.
    """

    if len(pw) < PASSWORD_MIN_LENGTH:
        raise ValueError(
            f"Password must be at least {PASSWORD_MIN_LENGTH} characters long"
        )
    if len(pw.encode("utf-8")) > PASSWORD_MAX_BYTES:
        raise ValueError(
            f"Password must be at most {PASSWORD_MAX_BYTES} bytes long"
        )
    if not any(c.isupper() for c in pw):
        raise ValueError("Password must contain an uppercase letter")
    if not any(c.islower() for c in pw):
        raise ValueError("Password must contain a lowercase letter")
    if not any(c.isdigit() for c in pw):
        raise ValueError("Password must contain a digit")
    return pw


def validate_username(value: Optional[str]) -> Optional[str]:
    """Normalise and check a submitted handle (UN-3), passing ``None`` through.

    ``None`` means "the caller offered no handle"; ``crud.create_user`` then
    derives one. Registration (UN-5) supplies one, so the form gets the
    user-facing message from :mod:`usernames` rather than a regex complaint.
    """
    if value is None:
        return None
    return usernames.validate(usernames.normalise(value))


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    display_name: Optional[str] = None
    # Optional on the wire so the existing clients and tests keep working; the
    # registration form sends it (UN-5) and Phase 3C makes it required in the UI.
    username: Optional[str] = None

    _check_password = field_validator("password")(validate_password)
    _check_username = field_validator("username")(validate_username)


class UserOut(BaseModel):
    id: int
    email: str
    username: str
    # D-7: ``username_changed_at IS NULL`` means the handle was system-assigned
    # and never confirmed, which is what the SPA's gate reads to force the
    # handle-selection step for a Google sign-up (UN-6).
    username_confirmed: bool = False
    display_name: Optional[str] = None
    auth_provider: str
    default_people: int
    email_verified: bool = False

    model_config = ConfigDict(from_attributes=True)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

    _check_password = field_validator("new_password")(validate_password)


class VerifyEmailRequest(BaseModel):
    token: str


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
    # Ingredient quantities are as authored, for ``servings`` people; see
    # ``models.Recipe``. Readers scale by ``target / servings``.
    title: str
    procedure: Optional[str] = None
    bulk_prep: bool = False
    course: str = "main"
    image_url: Optional[str] = None
    # The basis the quantities below were written for. Defaults to 1 so a client
    # that predates the field still describes its payload correctly.
    servings: int = Field(default=1, ge=1)
    tags: List[str] = []
    ingredients: List[IngredientIn] = []
    # Sides this main is habitually served with; the planner attaches one of
    # them automatically. Only meaningful for main / first-course recipes.
    favorite_side_ids: List[int] = []
    # VIS-2: private unless the caller says otherwise.
    visibility: str = "private"

    # AT-4: there is deliberately no ``source_author_username`` field here. The
    # attribution snapshot is write-once, set by the copy path alone; because
    # ``RecipeIn`` cannot carry it, no amount of subsequent editing can change
    # or remove it.

    @field_validator("visibility")
    @classmethod
    def _check_visibility(cls, value: str) -> str:
        if value == "public":
            # VIS-5. Rejected here rather than silently coerced, so a client
            # that tries it learns the capability does not exist yet.
            raise ValueError(PUBLIC_VISIBILITY_MESSAGE)
        if value not in VISIBILITY_VALUES:
            raise ValueError(f"Unknown visibility: {value!r}")
        return value


class RecipeOut(BaseModel):
    id: int
    title: str
    procedure: Optional[str] = None
    bulk_prep: bool
    course: str
    image_url: Optional[str] = None
    servings: int = 1
    score: Optional[float] = None
    date_last_consumed: Optional[date] = None
    ingredients: List[IngredientOut] = []
    tags: List[TagOut] = []
    # Read off ``Recipe.favorite_side_ids``, which flattens the relationship.
    favorite_side_ids: List[int] = []
    visibility: str = "private"
    # AT-3 / AT-7: the attribution snapshot and the copy counter have to reach
    # the authenticated recipe view -- that is where the credit line renders and
    # where the owner sees "copied N times".
    copy_count: int = 0
    source_author_username: Optional[str] = None
    source_recipe_title: Optional[str] = None
    copied_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class MealAssignment(BaseModel):
    main_id: int
    side_ids: List[int] = Field(default_factory=list)
    leftover: bool = False
    # The slot this meal occupies (Lunch=1, Dinner=2). Optional: callers that
    # send a day's meals in order can let position decide. Clients that drop an
    # empty slot before posting must send it, or the meals after the gap shift
    # up into the wrong slot.
    meal_number: Optional[int] = Field(default=None, ge=1, le=2)


class MealPlanCreate(BaseModel):
    plan_date: date
    plan: Dict[str, List[MealAssignment]]
    bulk_leftovers: bool | None = None
    keep_days: int | None = None


class FridgeItem(BaseModel):
    """An ingredient the user has on hand, with how many slots should use it."""

    ingredient_id: int
    count: int = Field(default=1, ge=1)


class MealPlanGenerate(BaseModel):
    start: date
    end: date
    meals_per_day: int
    fridge: List[FridgeItem] = []
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
