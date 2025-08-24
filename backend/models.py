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
from sqlalchemy.ext.associationproxy import association_proxy
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


class RecipeIngredient(Base):
    """Association object linking recipes and ingredients with quantities."""

    __tablename__ = "recipe_ingredients"

    id = Column(Integer, primary_key=True)
    recipe_id = Column(Integer, ForeignKey("recipes.id", ondelete="CASCADE"))
    ingredient_id = Column(Integer, ForeignKey("ingredients.id", ondelete="CASCADE"))
    quantity = Column(Float)

    recipe = relationship("Recipe", back_populates="recipe_ingredients")
    ingredient = relationship("Ingredient", back_populates="recipe_ingredients")

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

    recipe_ingredients = relationship(
        "RecipeIngredient",
        back_populates="recipe",
        cascade="all, delete-orphan",
    )
    ingredients = association_proxy(
        "recipe_ingredients",
        "ingredient",
        creator=lambda ing: RecipeIngredient(ingredient=ing, quantity=getattr(ing, "_quantity", None)),
    )
    tags = relationship(
        "Tag", secondary=recipe_tag_table, back_populates="recipes"
    )


class Ingredient(Base):
    """An ingredient used within a recipe."""

    __tablename__ = "ingredients"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    unit = Column(Enum(UnitEnum, name="unit_enum"))
    season_months = Column(IntList)

    recipe_ingredients = relationship(
        "RecipeIngredient", back_populates="ingredient"
    )

    def __init__(self, **kwargs):
        self._quantity = kwargs.pop("quantity", None)
        super().__init__(**kwargs)

    @property
    def quantity(self) -> float | None:
        if self.recipe_ingredients:
            return self.recipe_ingredients[0].quantity
        return self._quantity

    @quantity.setter
    def quantity(self, value: float | None) -> None:
        if self.recipe_ingredients:
            self.recipe_ingredients[0].quantity = value
        else:
            self._quantity = value

    @property
    def recipe_id(self) -> int | None:
        if self.recipe_ingredients:
            return self.recipe_ingredients[0].recipe_id
        return None


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
