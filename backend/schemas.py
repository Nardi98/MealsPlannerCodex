"""Pydantic schemas for API responses and requests."""
from __future__ import annotations

from datetime import date
from typing import Dict, List, Optional

from pydantic import BaseModel


class RecipeOut(BaseModel):
    id: int
    title: str
    servings_default: int
    procedure: Optional[str] = None
    bulk_prep: bool
    score: Optional[float] = None
    date_last_consumed: Optional[date] = None

    class Config:
        orm_mode = True


class TagOut(BaseModel):
    id: int
    name: str

    class Config:
        orm_mode = True


class MealPlanCreate(BaseModel):
    plan_date: date
    plan: Dict[str, List[int]]
