"""SQLAlchemy models for the Meals Planner Codex application."""

from __future__ import annotations

from datetime import date
from typing import List

from sqlalchemy import Boolean, Column, Date, Float, ForeignKey, Integer, String, Table, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base

# Association table for recipe-tag many-to-many relationship
recipe_tag_table = Table(
    "recipe_tag",
    Base.metadata,
    Column("recipe_id", ForeignKey("recipes.id"), primary_key=True),
    Column("tag_id", ForeignKey("tags.id"), primary_key=True),
)


class Recipe(Base):
    """Recipe model."""

    __tablename__ = "recipes"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    servings_default: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    procedure: Mapped[str | None] = mapped_column(Text)
    bulk_prep: Mapped[bool] = mapped_column(Boolean, default=False)
    score: Mapped[float | None] = mapped_column(Float)
    date_last_consumed: Mapped[date | None] = mapped_column(Date)

    ingredients: Mapped[List["Ingredient"]] = relationship(
        "Ingredient", back_populates="recipe", cascade="all, delete-orphan"
    )
    tags: Mapped[List["Tag"]] = relationship(
        "Tag", secondary=recipe_tag_table, back_populates="recipes"
    )


class Ingredient(Base):
    """Ingredient model."""

    __tablename__ = "ingredients"

    id: Mapped[int] = mapped_column(primary_key=True)
    recipe_id: Mapped[int] = mapped_column(ForeignKey("recipes.id"))
    name: Mapped[str] = mapped_column(String, nullable=False)
    quantity: Mapped[float | None] = mapped_column(Float)
    unit: Mapped[str | None] = mapped_column(String)
    season_months: Mapped[str | None] = mapped_column(String)

    recipe: Mapped[Recipe] = relationship("Recipe", back_populates="ingredients")


class Tag(Base):
    """Tag model."""

    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)

    recipes: Mapped[List[Recipe]] = relationship(
        "Recipe", secondary=recipe_tag_table, back_populates="tags"
    )
