"""Admin catalog curation routes (spec §9, §9.1, §10.2; plan D3).

Like :mod:`catalog_routes`, this module only translates HTTP to :mod:`catalog`
and back (CAT-1), and builds every body field by field from an explicit
allowlist (API-7/8). Every route sits behind :func:`auth_users.require_admin`
at the router level (ADM-4), so a non-admin gets one fixed 403 before any
route code runs, identical whatever the path names (PRV-5), and an anonymous
caller gets 401. Nothing here writes ``is_admin`` (ADM-2), and there is no
DELETE route: retiring is the only removal (API-14, RET-5).

Drafts: ``POST /recipes`` with ``"publish": false`` creates a system-owned
recipe with no catalog entry. It is not listed by ``GET /recipes``, which lists
entries (API-9); its id comes back in the 201 body, and it is reachable by
``PUT /recipes/{id}`` and ``POST /recipes/{id}/publish``.

Write routes commit on success. A service error raised after rows were flushed
(CAT-10's ``IncompleteRecipe`` on create or update) rolls back first, so a 400
never leaves a half-written recipe in the session.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Annotated, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.orm import Session

import auth_users
import catalog
import models
import ratelimit
from database import get_db

logger = logging.getLogger(__name__)

Db = Annotated[Session, Depends(get_db)]

#: The courses the app authors recipes in: the planner's main-slot courses and
#: sides (``models``), which is also the frontend's recipe-form vocabulary.
COURSES = (*models.MAIN_COURSES, models.SIDE_COURSE)


def _require_catalog(db: Db) -> None:
    """ERR-5: log the missing system account by name; the client gets a bare 500.

    A router dependency, listed after ``require_admin``, so a non-admin still
    gets the 403 and learns nothing about the catalog's state.
    """
    try:
        catalog.system_user(db)
    except catalog.SystemAccountMissing as exc:
        logger.error("catalog: no is_system account exists; the catalog cannot be curated (%s)", exc)
        raise HTTPException(status_code=500, detail="The recipe catalog is unavailable")


router = APIRouter(
    prefix="/admin/catalog",
    tags=["catalog-admin"],
    dependencies=[Depends(auth_users.require_admin), Depends(_require_catalog)],
)


# ---------------------------------------------------------------------------
# models (kept local to this router)
# ---------------------------------------------------------------------------
class IngredientLine(BaseModel):
    """One ingredient line; ``quantity`` is written for the recipe's ``servings``."""

    model_config = ConfigDict(extra="forbid")

    name: str
    quantity: float = Field(gt=0)
    unit: Literal["g", "ml", "piece"]


class RecipeWrite(BaseModel):
    """A catalog recipe as the admin form sends it.

    ``extra="forbid"``: a body carrying ``user_id``, ``visibility`` or
    ``is_admin`` is refused, never silently ignored. Ownership and visibility
    are the service's to set (SYS-6, P2-2). Ingredient and tag names must exist
    in the system account's vocabulary (D3).
    """

    model_config = ConfigDict(extra="forbid")

    title: str
    course: str
    servings: int = Field(ge=1)
    bulk_prep: bool
    procedure: Optional[str]
    image_url: Optional[str] = None
    tags: List[str]
    ingredients: List[IngredientLine]

    @field_validator("course")
    @classmethod
    def _known_course(cls, value: str) -> str:
        if value not in COURSES:
            raise ValueError(f"course must be one of {', '.join(COURSES)}")
        return value


class RecipeCreate(RecipeWrite):
    publish: bool = True


class AdminIngredient(BaseModel):
    """One ingredient line, in an admin row and in the export alike (units are stored as g|ml|piece)."""

    model_config = ConfigDict(extra="forbid")

    name: str
    quantity: Optional[float] = None
    unit: Optional[Literal["g", "ml", "piece"]] = None


class AdminRecipe(BaseModel):
    """AdminRow: a catalog row without ``in_my_book``, plus curation state (API-9).

    ``status``, ``published_at`` and ``retired_at`` are all null for a draft.
    """

    model_config = ConfigDict(extra="forbid")

    id: int
    title: str
    course: str
    servings: int
    bulk_prep: bool
    image_url: Optional[str] = None
    tags: List[str]
    ingredients: List[AdminIngredient]
    adoption_count: int
    procedure: Optional[str] = None
    status: Optional[Literal["published", "retired"]] = None
    published_at: Optional[datetime] = None
    retired_at: Optional[datetime] = None

    @classmethod
    def build(cls, row: catalog.CatalogRow) -> "AdminRecipe":
        recipe, entry = row.recipe, row.recipe.catalog_entry
        return cls(
            id=recipe.id,
            title=recipe.title,
            course=recipe.course,
            servings=recipe.servings,
            bulk_prep=bool(recipe.bulk_prep),
            image_url=recipe.image_url,
            tags=[tag.name for tag in recipe.tags],
            ingredients=[AdminIngredient(**line) for line in catalog.ingredient_lines(recipe)],
            adoption_count=row.adoption_count,
            procedure=recipe.procedure,
            status=entry.status if entry else None,
            published_at=entry.published_at if entry else None,
            retired_at=entry.retired_at if entry else None,
        )


class ExportItem(BaseModel):
    """One export entry: the pack's fields plus curation state, no user data (EXP-2..4)."""

    model_config = ConfigDict(extra="forbid")

    title: str
    course: str
    servings: int
    bulk_prep: bool
    tags: List[str]
    procedure: Optional[str] = None
    ingredients: List[AdminIngredient]
    status: Literal["published", "retired"]
    published_at: str
    retired_at: Optional[str] = None


class SystemIngredient(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    name: str
    season_months: List[int]
    grams_per_ml: Optional[float] = None
    grams_per_piece: Optional[float] = None
    preferred_dimension: Optional[str] = None


class SystemTag(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    name: str


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _admin_row(db: Session, recipe: models.Recipe) -> AdminRecipe:
    count = catalog.adoption_counts(db, [recipe.id])[recipe.id]
    return AdminRecipe.build(catalog.CatalogRow(recipe, count))


def _recipe_or_404(db: Session, recipe_id: int) -> models.Recipe:
    recipe = db.get(models.Recipe, recipe_id)
    if recipe is None:
        raise HTTPException(status_code=404, detail="Not found")
    return recipe


# ---------------------------------------------------------------------------
# routes
# ---------------------------------------------------------------------------
@router.get("/recipes", response_model=List[AdminRecipe])
def list_catalog_entries(db: Db) -> List[AdminRecipe]:
    """Every entry, published and retired, with its status and adoption count (API-9)."""
    return [AdminRecipe.build(row) for row in catalog.list_all(db)]


@router.post("/recipes", response_model=AdminRecipe, status_code=201)
@ratelimit.limiter.limit(ratelimit.CATALOG_ADMIN_RATE_LIMIT)
def create_catalog_recipe(request: Request, payload: RecipeCreate, db: Db) -> AdminRecipe:
    """A system-owned recipe, published unless ``publish`` is false (API-10)."""
    try:
        recipe = catalog.create_catalog_recipe(
            db, payload.model_dump(exclude={"publish"}), publish=payload.publish
        )
    except ValueError as exc:  # an unknown name, or IncompleteRecipe (ERR-6)
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
    db.commit()
    return _admin_row(db, recipe)


@router.put("/recipes/{recipe_id}", response_model=AdminRecipe)
@ratelimit.limiter.limit(ratelimit.CATALOG_ADMIN_RATE_LIMIT)
def update_catalog_recipe(request: Request, recipe_id: int, payload: RecipeWrite, db: Db) -> AdminRecipe:
    """Rewrite a system-owned recipe; 404 for anyone else's (API-11)."""
    try:
        recipe = catalog.update_catalog_recipe(db, recipe_id, payload.model_dump())
    except catalog.CatalogEntryNotFound:
        raise HTTPException(status_code=404, detail="Not found")
    except ValueError as exc:  # an unknown name, or a published entry made incomplete
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
    db.commit()
    return _admin_row(db, recipe)


@router.post("/recipes/{recipe_id}/publish", response_model=AdminRecipe)
@ratelimit.limiter.limit(ratelimit.CATALOG_ADMIN_RATE_LIMIT)
def publish_catalog_recipe(request: Request, recipe_id: int, db: Db) -> AdminRecipe:
    """CAT-6/7: publish a draft or bring a retired entry back (API-12)."""
    recipe = _recipe_or_404(db, recipe_id)
    try:
        catalog.publish(db, recipe)
    except PermissionError:  # CAT-9 / ERR-7 / ADM-8
        raise HTTPException(status_code=403, detail="Only the recipe library's own recipes can be published")
    except catalog.IncompleteRecipe as exc:  # CAT-10 / ERR-6
        raise HTTPException(status_code=400, detail=str(exc))
    db.commit()
    return _admin_row(db, recipe)


@router.post("/recipes/{recipe_id}/retire", response_model=AdminRecipe)
@ratelimit.limiter.limit(ratelimit.CATALOG_ADMIN_RATE_LIMIT)
def retire_catalog_recipe(request: Request, recipe_id: int, db: Db) -> AdminRecipe:
    """CAT-8: hide an entry from the catalog, keeping the recipe and its count (API-12)."""
    recipe = _recipe_or_404(db, recipe_id)
    try:
        catalog.retire(db, recipe)
    except catalog.CatalogEntryNotFound:
        raise HTTPException(status_code=404, detail="Not found")
    db.commit()
    return _admin_row(db, recipe)


@router.get("/export", response_model=List[ExportItem])
def export_catalog(db: Db) -> List[ExportItem]:
    """The whole catalog as a pack-compatible JSON array (§9.1, API-13)."""
    return [ExportItem(**item) for item in catalog.export_catalog(db)]


@router.get("/ingredients", response_model=List[SystemIngredient])
def list_system_ingredients(db: Db) -> List[SystemIngredient]:
    """The system account's ingredients: the names a catalog recipe may use (D3)."""
    return [
        SystemIngredient(
            id=ingredient.id,
            name=ingredient.name,
            season_months=ingredient.season_months or [],
            grams_per_ml=ingredient.grams_per_ml,
            grams_per_piece=ingredient.grams_per_piece,
            preferred_dimension=(
                ingredient.preferred_dimension.value if ingredient.preferred_dimension is not None else None
            ),
        )
        for ingredient in catalog.system_ingredients(db)
    ]


@router.get("/tags", response_model=List[SystemTag])
def list_system_tags(db: Db) -> List[SystemTag]:
    """The system account's tags: the tag names a catalog recipe may use (D3)."""
    return [SystemTag(id=tag.id, name=tag.name) for tag in catalog.system_tags(db)]
