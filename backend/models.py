"""SQLAlchemy models for the Meals Planner Codex application."""

from __future__ import annotations

from enum import Enum as PyEnum

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.types import TypeDecorator

from database import Base


class IntList(TypeDecorator):
    """Store ``list[int]`` values as comma separated strings."""

    impl = String

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return ",".join(str(int(v)) for v in value)

    def process_result_value(self, value, dialect):
        if not value:
            return []
        return [int(v) for v in value.split(",") if v]


# Association table linking recipes and tags for a many-to-many relationship.
recipe_tag_table = Table(
    "recipe_tag",
    Base.metadata,
    Column("recipe_id", ForeignKey("recipes.id"), primary_key=True),
    Column("tag_id", ForeignKey("tags.id"), primary_key=True),
)


class UnitEnum(str, PyEnum):
    """Allowed measurement units for ingredients."""

    G = "g"
    KG = "kg"
    L = "l"
    ML = "ml"
    PIECE = "piece"


class Recipe(Base):
    """A meal that can be prepared and consumed."""

    __tablename__ = "recipes"

    id = Column(Integer, primary_key=True)
    title = Column(String, nullable=False)
    servings_default = Column(Integer, nullable=False)
    procedure = Column(Text)
    bulk_prep = Column(Boolean, default=False)
    score = Column(Float)
    date_last_consumed = Column(Date)

    # Relationship to ``RecipeIngredient`` association objects.
    ingredients = relationship(
        "RecipeIngredient", back_populates="recipe", cascade="all, delete-orphan"
    )
    tags = relationship(
        "Tag", secondary=recipe_tag_table, back_populates="recipes"
    )


class Ingredient(Base):
    """A unique ingredient that can appear in many recipes."""

    __tablename__ = "ingredients"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, unique=True)
    season_months = Column(IntList)

    recipes = relationship(
        "RecipeIngredient", back_populates="ingredient", cascade="all, delete-orphan"
    )


class RecipeIngredient(Base):
    """Association table linking recipes and ingredients with quantities."""

    __tablename__ = "recipe_ingredients"

    recipe_id = Column(
        Integer, ForeignKey("recipes.id", ondelete="CASCADE"), primary_key=True
    )
    ingredient_id = Column(
        Integer, ForeignKey("ingredients.id", ondelete="CASCADE"), primary_key=True
    )
    quantity = Column(Float)
    unit = Column(Enum(UnitEnum, name="unit_enum"))

    recipe = relationship("Recipe", back_populates="ingredients")
    ingredient = relationship("Ingredient", back_populates="recipes")

    # Convenience accessors so Pydantic schemas can read attributes directly
    @property
    def id(self) -> int:  # pragma: no cover - simple delegation
        return self.ingredient_id

    @property
    def name(self) -> str:  # pragma: no cover - simple delegation
        return self.ingredient.name

    @property
    def season_months(self) -> list[int] | None:  # pragma: no cover
        return self.ingredient.season_months


class Tag(Base):
    """A simple label that can be attached to recipes."""

    __tablename__ = "tags"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, unique=True)

    recipes = relationship(
        "Recipe", secondary=recipe_tag_table, back_populates="tags"
    )


class MealPlan(Base):
    """A dated collection of planned meals."""

    __tablename__ = "meal_plans"

    id = Column(Integer, primary_key=True)
    plan_date = Column(Date, nullable=False, unique=True)

    slots = relationship(
        "MealSlot", back_populates="plan", cascade="all, delete-orphan"
    )


class MealSlot(Base):
    """A specific meal time within a :class:`MealPlan`."""

    __tablename__ = "meal_slots"

    id = Column(Integer, primary_key=True)
    meal_plan_id = Column(
        Integer, ForeignKey("meal_plans.id", ondelete="CASCADE"), nullable=False
    )
    meal_time = Column(String, nullable=False)
    recipe_id = Column(Integer, ForeignKey("recipes.id"))

    plan = relationship("MealPlan", back_populates="slots")
    recipe = relationship("Recipe")
