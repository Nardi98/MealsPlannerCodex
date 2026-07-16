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
    JSON,
    PrimaryKeyConstraint,
    String,
    Table,
    Text,
    UniqueConstraint,
    false,
    func,
)
from sqlalchemy.orm import relationship, validates
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


class StrList(TypeDecorator):
    """Store ``list[str]`` values as comma separated strings."""

    impl = String

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return ",".join(str(v) for v in value)

    def process_result_value(self, value, dialect):
        if not value:
            return []
        return [v for v in value.split(",") if v]


#: Canonical, ordered set of ingredient categories. Single source of truth for
#: the backend; the frontend mirrors this list in ``constants/categories.js``.
CATEGORIES: tuple[str, ...] = (
    "Vegetables",
    "Fruit",
    "Meat",
    "Fish",
    "Dairy & Eggs",
    "Grains & Pasta",
    "Legumes",
    "Herbs & Spices",
    "Condiments & Oils",
    "Nuts & Seeds",
    "Sweets & Sugar",
    "Beverages",
    "Protein",
    "Fiber",
    "Carbs",
    "Plant-based",
    "High-calorie",
)


def _owner_fk_column(*, index: bool = True) -> Column:
    """A nullable ``user_id`` FK to ``users`` for an owned resource.

    Each mapped class needs its own ``Column`` instance, so this is a factory
    rather than a shared column.

    Pass ``index=False`` where the table already declares a
    ``UniqueConstraint("user_id", ...)``: that constraint's index leads with
    ``user_id`` and already serves the ownership filter, so a standalone index
    would just be a second B-tree to maintain on every write.
    """

    return Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=index)


def normalize_email(email: str) -> str:
    """Return the canonical stored form of ``email``: trimmed and lowercased.

    Every read and write funnels through here so stored values and lookup keys
    always match. Addresses are treated as case-insensitive in full: only the
    domain is formally case-insensitive, but no provider we target distinguishes
    the local part, and folding it whole is what users expect.
    """
    return email.strip().lower()


class User(Base):
    """An account owning its own recipes, ingredients, tags, and plans."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String, nullable=False, unique=True, index=True)
    # Null for OAuth-only accounts (e.g. Google sign-in).
    hashed_password = Column(String, nullable=True)
    display_name = Column(String)
    auth_provider = Column(String, nullable=False, default="local")
    google_sub = Column(String, nullable=True, unique=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    # Per-user overrides layered on top of ``DEFAULT_PLAN_SETTINGS``. ``None``
    # means "no overrides" (the account uses the shared defaults).
    plan_settings = Column(JSON, nullable=True)

    @validates("email")
    def _canonicalise_email(self, key: str, value: str) -> str:
        # On the model rather than in ``crud`` so that every write path obeys
        # it, including the seed scripts that construct ``User`` directly. The
        # unique index then enforces case-insensitive uniqueness by
        # construction rather than by luck of lowercase literals.
        return normalize_email(value)


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
    user_id = _owner_fk_column()
    title = Column(String, nullable=False)
    servings_default = Column(Integer, nullable=False)
    procedure = Column(Text)
    bulk_prep = Column(Boolean, default=False)
    score = Column(Float)
    date_last_consumed = Column(Date)
    date_last_rejected = Column(Date)
    course = Column(String, nullable=False, default="main")
    image_url = Column(String, nullable=True)

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
    # uq_ingredient_user_name already indexes (user_id, name).
    user_id = _owner_fk_column(index=False)
    name = Column(String, nullable=False)
    season_months = Column(IntList)
    unit = Column(Enum(UnitEnum, name="unit_enum"))
    categories = Column(StrList, nullable=True)

    recipes = relationship(
        "RecipeIngredient", back_populates="ingredient", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_ingredient_user_name"),
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
    # uq_tag_user_name already indexes (user_id, name).
    user_id = _owner_fk_column(index=False)
    name = Column(String, nullable=False)
    penalize_repetition = Column(Boolean, nullable=False, server_default=false())
    is_system = Column(Boolean, nullable=False, server_default=false())

    recipes = relationship(
        "Recipe", secondary=recipe_tag_table, back_populates="tags"
    )

    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_tag_user_name"),
    )


class MealPlan(Base):
    """A dated collection of planned meals."""

    __tablename__ = "meal_plans"

    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    plan_date = Column(Date, nullable=False)

    meals = relationship(
        "Meal", back_populates="plan", cascade="all, delete-orphan"
    )

    __table_args__ = (
        PrimaryKeyConstraint("user_id", "plan_date"),
    )


class Meal(Base):
    """A specific meal within a :class:`MealPlan`."""

    __tablename__ = "meals"

    user_id = Column(Integer, nullable=False)
    plan_date = Column(Date, nullable=False)
    meal_number = Column(Integer, nullable=False)
    recipe_id = Column(Integer, ForeignKey("recipes.id"))
    accepted = Column(Boolean, default=False)
    # A meal is a leftover iff it links back to the source meal that produced
    # it. The two columns are all-or-nothing (see the CHECK constraint below);
    # ``leftover`` is derived from their presence rather than stored separately.
    leftover_source_date = Column(Date, nullable=True)
    leftover_source_meal = Column(Integer, nullable=True)

    plan = relationship("MealPlan", back_populates="meals")
    recipe = relationship("Recipe", foreign_keys=[recipe_id])
    sides = relationship(
        "MealSide",
        back_populates="meal",
        cascade="all, delete-orphan",
        order_by="MealSide.position",
    )

    __table_args__ = (
        PrimaryKeyConstraint("user_id", "plan_date", "meal_number"),
        ForeignKeyConstraint(
            ["user_id", "plan_date"],
            ["meal_plans.user_id", "meal_plans.plan_date"],
            ondelete="CASCADE",
        ),
        CheckConstraint("meal_number IN (1,2)"),
        CheckConstraint(
            "(leftover_source_date IS NULL) = (leftover_source_meal IS NULL)",
            name="ck_meal_leftover_source_all_or_nothing",
        ),
    )

    @property
    def leftover(self) -> bool:
        """A meal is a leftover exactly when it links to a source meal."""
        return self.leftover_source_date is not None

    @property
    def side_recipe(self):
        return self.sides[0].side_recipe if self.sides else None

    @property
    def side_recipe_id(self):
        return self.sides[0].side_recipe_id if self.sides else None


class MealSide(Base):
    """Side dishes associated with a :class:`Meal`."""

    __tablename__ = "meal_side_dishes"

    user_id = Column(Integer, nullable=False)
    plan_date = Column(Date, nullable=False)
    meal_number = Column(Integer, nullable=False)
    position = Column(Integer, nullable=False)
    side_recipe_id = Column(Integer, ForeignKey("recipes.id"), nullable=False)

    meal = relationship("Meal", back_populates="sides")
    side_recipe = relationship("Recipe")

    __table_args__ = (
        PrimaryKeyConstraint("user_id", "plan_date", "meal_number", "position"),
        ForeignKeyConstraint(
            ["user_id", "plan_date", "meal_number"],
            ["meals.user_id", "meals.plan_date", "meals.meal_number"],
            ondelete="CASCADE",
        ),
    )
