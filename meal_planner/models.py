"""Simplified data models for the meal planner.

These dataclasses provide a starting point for the system without relying on
third-party ORM dependencies.  They are deliberately lightweight and do not
perform any database persistence, but they capture the key relationships
required by higher-level services.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import List, Optional


@dataclass
class Tag:
    name: str
    id: Optional[int] = None
    recipes: List["Recipe"] = field(default_factory=list)


@dataclass
class Ingredient:
    name: str
    id: Optional[int] = None
    category: Optional[str] = None
    density_g_per_ml: Optional[float] = None
    typical_item_mass_g: Optional[float] = None
    season_months: List[int] = field(default_factory=list)


@dataclass
class RecipeIngredient:
    ingredient: Ingredient
    qty_value: float
    qty_unit: str
    note: Optional[str] = None
    id: Optional[int] = None


@dataclass
class Recipe:
    title: str
    servings_default: int
    prep_time_min: int
    bulk_preparation: bool = False
    instructions: Optional[str] = None
    notes: Optional[str] = None
    id: Optional[int] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    tags: List[Tag] = field(default_factory=list)
    ingredients: List[RecipeIngredient] = field(default_factory=list)


@dataclass
class PlanItem:
    date: date
    meal_type: str
    recipe: Optional[Recipe] = None
    servings_override: Optional[int] = None
    leftover_of: Optional["PlanItem"] = None
    leftover_portions: Optional[int] = None
    id: Optional[int] = None


@dataclass
class MealPlan:
    start_date: date
    days: int
    meals_per_day: List[str]
    id: Optional[int] = None
    items: List[PlanItem] = field(default_factory=list)


@dataclass
class RecipeUsage:
    recipe: Recipe
    used_on: date
    id: Optional[int] = None


@dataclass
class Feedback:
    plan_item: PlanItem
    accepted: bool
    rating_1_5: Optional[int] = None
    comments: Optional[str] = None
    id: Optional[int] = None


@dataclass
class UserProfile:
    dietary_include_tags: List[str] = field(default_factory=list)
    dietary_exclude_tags: List[str] = field(default_factory=list)
    time_budget_per_meal_min: Optional[int] = None
    leftover_window_days: int = 3
    repeat_spacing_k_days: int = 3
    id: int = 1
