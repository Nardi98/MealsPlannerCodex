"""SQLAlchemy models for the Meals Planner Codex application."""

from __future__ import annotations

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    Float,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
)
from sqlalchemy.orm import relationship

from .database import Base

# Association table linking recipes and tags for a many-to-many relationship.
recipe_tag_table = Table(
    "recipe_tag",
    Base.metadata,
    Column("recipe_id", ForeignKey("recipes.id"), primary_key=True),
    Column("tag_id", ForeignKey("tags.id"), primary_key=True),
)


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

    ingredients = relationship(
        "Ingredient", back_populates="recipe", cascade="all, delete-orphan"
    )
    tags = relationship(
        "Tag", secondary=recipe_tag_table, back_populates="recipes"
    )


class Ingredient(Base):
    """An ingredient used within a recipe."""

    __tablename__ = "ingredients"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    quantity = Column(Float)
    unit = Column(String)
    season_months = Column(String)
    recipe_id = Column(Integer, ForeignKey("recipes.id", ondelete="CASCADE"))

    recipe = relationship("Recipe", back_populates="ingredients")


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

