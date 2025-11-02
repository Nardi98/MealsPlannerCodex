"""SQLAlchemy models for the Meals Planner Codex application."""

from __future__ import annotations

from enum import Enum as PyEnum

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    CheckConstraint,
    PrimaryKeyConstraint,
    String,
    Table,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy import and_
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
    Column("user_id", Integer, nullable=False),
    Column("recipe_id", Integer, nullable=False),
    Column("tag_id", Integer, nullable=False),
    PrimaryKeyConstraint("user_id", "recipe_id", "tag_id"),
    ForeignKeyConstraint(
        ["user_id", "recipe_id"],
        ["recipes.user_id", "recipes.id"],
        ondelete="CASCADE",
    ),
    ForeignKeyConstraint(
        ["user_id", "tag_id"],
        ["tags.user_id", "tags.id"],
        ondelete="CASCADE",
    ),
)


class UnitEnum(str, PyEnum):
    """Allowed measurement units for ingredients."""

    G = "g"
    KG = "kg"
    L = "l"
    ML = "ml"
    PIECE = "piece"


class User(Base):
    """Application user owning recipes, ingredients, and plans."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String, nullable=False, unique=True)
    username = Column(String, nullable=False, unique=True)
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    recipes = relationship(
        "Recipe", back_populates="user", cascade="all, delete-orphan"
    )
    ingredients = relationship(
        "Ingredient", back_populates="user", cascade="all, delete-orphan"
    )
    tags = relationship("Tag", back_populates="user", cascade="all, delete-orphan")
    meal_plans = relationship(
        "MealPlan", back_populates="user", cascade="all, delete-orphan"
    )
    meals = relationship("Meal", back_populates="user", cascade="all, delete-orphan")


class Recipe(Base):
    """A meal that can be prepared and consumed."""

    __tablename__ = "recipes"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String, nullable=False)
    servings_default = Column(Integer, nullable=False)
    procedure = Column(Text)
    bulk_prep = Column(Boolean, default=False)
    score = Column(Float)
    date_last_consumed = Column(Date)
    course = Column(String, nullable=False, default="main")

    __table_args__ = (
        UniqueConstraint("user_id", "id"),
        UniqueConstraint("user_id", "title"),
    )

    # Relationship to ``RecipeIngredient`` association objects.
    ingredients = relationship(
        "RecipeIngredient",
        back_populates="recipe",
        cascade="all, delete-orphan",
        primaryjoin=lambda: and_(
            Recipe.id == RecipeIngredient.recipe_id,
            Recipe.user_id == RecipeIngredient.user_id,
        ),
    )
    tags = relationship(
        "Tag",
        secondary=recipe_tag_table,
        back_populates="recipes",
        primaryjoin=lambda: and_(
            Recipe.id == recipe_tag_table.c.recipe_id,
            Recipe.user_id == recipe_tag_table.c.user_id,
        ),
        secondaryjoin=lambda: and_(
            Tag.id == recipe_tag_table.c.tag_id,
            Tag.user_id == recipe_tag_table.c.user_id,
        ),
    )
    user = relationship("User", back_populates="recipes")


class Ingredient(Base):
    """A unique ingredient that can appear in many recipes."""

    __tablename__ = "ingredients"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    season_months = Column(IntList)
    unit = Column(Enum(UnitEnum, name="unit_enum"))

    __table_args__ = (
        UniqueConstraint("user_id", "id"),
        UniqueConstraint("user_id", "name"),
    )

    recipes = relationship(
        "RecipeIngredient",
        back_populates="ingredient",
        cascade="all, delete-orphan",
        primaryjoin=lambda: and_(
            Ingredient.id == RecipeIngredient.ingredient_id,
            Ingredient.user_id == RecipeIngredient.user_id,
        ),
    )
    user = relationship("User", back_populates="ingredients")


class RecipeIngredient(Base):
    """Association table linking recipes and ingredients with quantities."""

    __tablename__ = "recipe_ingredients"

    user_id = Column(Integer, nullable=False)
    recipe_id = Column(Integer, nullable=False)
    ingredient_id = Column(Integer, nullable=False)
    quantity = Column(Float)
    unit = Column(Enum(UnitEnum, name="unit_enum"))

    __table_args__ = (
        PrimaryKeyConstraint("user_id", "recipe_id", "ingredient_id"),
        ForeignKeyConstraint(
            ["user_id", "recipe_id"],
            ["recipes.user_id", "recipes.id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["user_id", "ingredient_id"],
            ["ingredients.user_id", "ingredients.id"],
            ondelete="CASCADE",
        ),
    )

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
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "id"),
        UniqueConstraint("user_id", "name"),
    )

    recipes = relationship(
        "Recipe",
        secondary=recipe_tag_table,
        back_populates="tags",
        primaryjoin=lambda: and_(
            Tag.id == recipe_tag_table.c.tag_id,
            Tag.user_id == recipe_tag_table.c.user_id,
        ),
        secondaryjoin=lambda: and_(
            Recipe.id == recipe_tag_table.c.recipe_id,
            Recipe.user_id == recipe_tag_table.c.user_id,
        ),
    )
    user = relationship("User", back_populates="tags")


class MealPlan(Base):
    """A dated collection of planned meals."""

    __tablename__ = "meal_plans"

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    plan_date = Column(Date, nullable=False)

    __table_args__ = (PrimaryKeyConstraint("user_id", "plan_date"),)

    meals = relationship(
        "Meal", back_populates="plan", cascade="all, delete-orphan"
    )
    user = relationship("User", back_populates="meal_plans")


class Meal(Base):
    """A specific meal within a :class:`MealPlan`."""

    __tablename__ = "meals"

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    plan_date = Column(Date, nullable=False)
    meal_number = Column(Integer, nullable=False)
    recipe_id = Column(Integer)
    accepted = Column(Boolean, default=False)
    leftover = Column(Boolean, default=False)

    plan = relationship("MealPlan", back_populates="meals")
    recipe = relationship(
        "Recipe",
        foreign_keys=[recipe_id],
        primaryjoin=lambda: and_(
            Recipe.id == Meal.recipe_id,
            Recipe.user_id == Meal.user_id,
        ),
    )
    sides = relationship(
        "MealSide",
        back_populates="meal",
        cascade="all, delete-orphan",
        order_by="MealSide.position",
    )
    user = relationship("User", back_populates="meals")

    __table_args__ = (
        PrimaryKeyConstraint("user_id", "plan_date", "meal_number"),
        ForeignKeyConstraint(
            ["user_id", "plan_date"],
            ["meal_plans.user_id", "meal_plans.plan_date"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["user_id", "recipe_id"],
            ["recipes.user_id", "recipes.id"],
        ),
        CheckConstraint("meal_number IN (1,2)"),
    )

    @property
    def side_recipe(self):
        return self.sides[0].side_recipe if self.sides else None

    @property
    def side_recipe_id(self):
        return self.sides[0].side_recipe_id if self.sides else None


class MealSide(Base):
    """Side dishes associated with a :class:`Meal`."""

    __tablename__ = "meal_side_dishes"

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    plan_date = Column(Date, nullable=False)
    meal_number = Column(Integer, nullable=False)
    position = Column(Integer, nullable=False)
    side_recipe_id = Column(Integer, nullable=False)

    meal = relationship("Meal", back_populates="sides")
    side_recipe = relationship(
        "Recipe",
        primaryjoin=lambda: and_(
            Recipe.id == MealSide.side_recipe_id,
            Recipe.user_id == MealSide.user_id,
        ),
    )

    __table_args__ = (
        PrimaryKeyConstraint("user_id", "plan_date", "meal_number", "position"),
        ForeignKeyConstraint(
            ["user_id", "plan_date", "meal_number"],
            ["meals.user_id", "meals.plan_date", "meals.meal_number"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["user_id", "side_recipe_id"],
            ["recipes.user_id", "recipes.id"],
        ),
    )
