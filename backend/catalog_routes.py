"""User-facing catalog routes: browse, detail and adopt (spec §10.1).

This module only translates HTTP to :mod:`catalog` and back (CAT-1). Its one
job of its own is the response shape: every body is built field by field from
an explicit allowlist, never from the ORM row or ``schemas.RecipeOut``, so a
future ``Recipe`` column cannot leak into the catalog, and nothing identifying
the system account -- its handle, email or id -- is ever serialised (API-7/8,
PRV-3). Every route requires authentication (P2-4).
"""

from __future__ import annotations

import logging
from typing import Annotated, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

import auth_users
import catalog
import models
import ratelimit
from database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/catalog", tags=["catalog"])

Db = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[models.User, Depends(auth_users.get_current_user)]


# ---------------------------------------------------------------------------
# models (kept local to this router)
# ---------------------------------------------------------------------------
class CatalogIngredient(BaseModel):
    """One ingredient line; ``quantity`` is written for the recipe's ``servings``."""

    model_config = ConfigDict(extra="forbid")

    name: str
    quantity: Optional[float] = None
    unit: Optional[Literal["g", "ml", "piece"]] = None


class CatalogRecipe(BaseModel):
    """A catalog listing row (API-2): a menu item, not a recipe record (API-8)."""

    model_config = ConfigDict(extra="forbid")

    id: int
    title: str
    course: str
    servings: int
    bulk_prep: bool
    image_url: Optional[str] = None
    tags: List[str]
    ingredients: List[CatalogIngredient]
    adoption_count: int
    in_my_book: bool

    @classmethod
    def build(cls, row: catalog.CatalogRow, in_my_book: bool, **extra) -> "CatalogRecipe":
        recipe = row.recipe
        return cls(
            id=recipe.id,
            title=recipe.title,
            course=recipe.course,
            servings=recipe.servings,
            bulk_prep=bool(recipe.bulk_prep),
            image_url=recipe.image_url,
            tags=[tag.name for tag in recipe.tags],
            ingredients=[CatalogIngredient(**line) for line in catalog.ingredient_lines(recipe)],
            adoption_count=row.adoption_count,
            in_my_book=in_my_book,
            **extra,
        )


class CatalogRecipeDetail(CatalogRecipe):
    """The detail view: a listing row plus the procedure (API-4, API-5)."""

    procedure: Optional[str] = None


class AdoptIn(BaseModel):
    """No ``min_length``: an empty list is the service's 400, with its message (ERR-2)."""

    model_config = ConfigDict(extra="forbid")

    recipe_ids: List[int]


class AdoptOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    created_ids: List[int]
    skipped_ids: List[int]


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _catalog_unavailable(exc: catalog.SystemAccountMissing) -> HTTPException:
    """ERR-5: log the missing system account by name; the client gets a bare 500."""
    logger.error("catalog: no is_system account exists; the catalog cannot be served (%s)", exc)
    return HTTPException(status_code=500, detail="The recipe catalog is unavailable")


# ---------------------------------------------------------------------------
# routes
# ---------------------------------------------------------------------------
@router.get("/recipes", response_model=List[CatalogRecipe])
def list_catalog_recipes(
    db: Db,
    current_user: CurrentUser,
    course: Annotated[Optional[List[str]], Query()] = None,
    tags: Annotated[Optional[List[str]], Query()] = None,
    q: Optional[str] = None,
    sort: catalog.Sort = "popular",
) -> List[CatalogRecipe]:
    """Published entries, filtered and sorted (API-1), capped at ``catalog.LISTING_CAP``.

    ``in_my_book`` is one ``held_by`` query for the whole listing (API-3).
    """
    try:
        rows = catalog.list_published(db, course=course, tags=tags, query=q, sort=sort)
    except catalog.SystemAccountMissing as exc:
        raise _catalog_unavailable(exc)
    held = catalog.held_by(db, current_user, [row.recipe.id for row in rows]) if rows else set()
    return [CatalogRecipe.build(row, row.recipe.id in held) for row in rows]


@router.get("/recipes/{recipe_id}", response_model=CatalogRecipeDetail)
def get_catalog_recipe(recipe_id: int, db: Db, current_user: CurrentUser) -> CatalogRecipeDetail:
    """One published entry with its procedure; 404 for anything else (API-5)."""
    try:
        row = catalog.get_published(db, recipe_id)
    except catalog.SystemAccountMissing as exc:
        raise _catalog_unavailable(exc)
    except catalog.CatalogEntryNotFound:
        raise HTTPException(status_code=404, detail="Not found")
    in_my_book = recipe_id in catalog.held_by(db, current_user, [recipe_id])
    return CatalogRecipeDetail.build(row, in_my_book, procedure=row.recipe.procedure)


@router.post("/adopt", response_model=AdoptOut)
@ratelimit.limiter.limit(ratelimit.CATALOG_ADOPT_RATE_LIMIT)
def adopt_catalog_recipes(
    request: Request,
    payload: AdoptIn,
    db: Db,
    current_user: CurrentUser,
) -> AdoptOut:
    """Copy published entries into the caller's book in one transaction (API-6, §8).

    ``request`` is unused by the body and required by slowapi (ADO-13). Any id
    that is not a published entry fails the whole batch with 404, so this is
    never a general-purpose recipe copier (ADO-14, PRV-6).
    """
    try:
        result = catalog.adopt(db, current_user, payload.recipe_ids)
    except catalog.SystemAccountMissing as exc:
        raise _catalog_unavailable(exc)
    except catalog.CatalogEntryNotFound:
        raise HTTPException(status_code=404, detail="Not found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return AdoptOut(created_ids=result.created_ids, skipped_ids=result.skipped_ids)
