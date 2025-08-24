"""Pydantic schemas for API responses and requests."""
from __future__ import annotations

from datetime import date
from typing import Dict, List, Optional

from pydantic import BaseModel


class TagOut(BaseModel):
    id: int
    name: str

    class Config:
        orm_mode = True


class IngredientOut(BaseModel):
    id: int
    name: str
    quantity: Optional[float] = None
    unit: Optional[str] = None
    season_months: Optional[str] = None

    class Config:
        orm_mode = True


class IngredientIn(BaseModel):
    name: str
    quantity: Optional[float] = None
    unit: Optional[str] = None
    season_months: Optional[str] = None


class RecipeIn(BaseModel):
    title: str
    servings_default: int
    procedure: Optional[str] = None
    bulk_prep: bool = False
    tags: List[str] = []
    ingredients: List[IngredientIn] = []


class RecipeOut(BaseModel):
    id: int
    title: str
    servings_default: int
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
