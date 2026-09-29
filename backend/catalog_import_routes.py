"""HTTP for the reviewed catalog import (plan phase 3).

Like :mod:`catalog_admin_routes`, this module only translates HTTP to
:mod:`catalog_import` and back, and builds every body field by field from an
explicit allowlist. Every route sits behind :func:`auth_users.require_admin` and
the catalog's availability check at the *router* level, so a non-admin gets one
fixed 403 before any route code runs, identical whatever the path names, and an
anonymous caller gets 401.

**Prefix.** ``/admin/catalog/imports``, a path under ``/admin/catalog`` as the
plan specified. Abandoning a batch is a ``DELETE``; the admin catalog's
no-DELETE contract covers ``/admin/catalog/recipes`` (retiring is the only
removal a *recipe* has), not the import batches.

**Upload is not multipart.** The body is the already-parsed JSON array plus the
filename, following ``POST /data/import``: the browser parses the file, as
``ImportExportPage.jsx`` already does.

Write routes commit on success. A service error raised after rows were flushed
rolls back first, so a 400 never leaves half a staged batch in the session.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

import auth_users
import catalog
import catalog_import
import models
import ratelimit
from catalog_admin_routes import _require_catalog
from database import get_db

Db = Annotated[Session, Depends(get_db)]

router = APIRouter(
    prefix="/admin/catalog/imports",
    tags=["catalog-import"],
    dependencies=[Depends(auth_users.require_admin), Depends(_require_catalog)],
)


# ---------------------------------------------------------------------------
# models (kept local to this router)
# ---------------------------------------------------------------------------
class UploadRequest(BaseModel):
    """A parsed JSON file: its name, and the entries it held.

    ``extra="forbid"``: a body carrying ``publish`` or anything else the import
    does not honour is refused, never silently ignored. Entries are typed
    ``Any`` on purpose -- validating them here would reject the whole file for
    one bad entry, and staging a bad entry with its reason is the point.
    """

    model_config = ConfigDict(extra="forbid")

    filename: str
    entries: List[Any]


class DraftWrite(BaseModel):
    """The admin's working copy, as the review page sends it back."""

    model_config = ConfigDict(extra="forbid")

    draft: Any


class ItemSummary(BaseModel):
    """One staged entry as the batch overview lists it."""

    model_config = ConfigDict(extra="forbid")

    id: int
    position: int
    title: Optional[str] = None
    state: str
    error: Optional[str] = None
    problems: List[str]
    duplicate_recipe_id: Optional[int] = None
    committed_recipe_id: Optional[int] = None


class DuplicateRecipe(BaseModel):
    """The existing catalog recipe an incoming entry collides with.

    Enough of it to render the side-by-side comparison, and nothing else.
    """

    model_config = ConfigDict(extra="forbid")

    id: int
    title: str
    course: str
    servings: int
    bulk_prep: bool
    image_url: Optional[str] = None
    procedure: Optional[str] = None
    tags: List[str]
    ingredients: List[Dict[str, Any]]


class ItemDetail(ItemSummary):
    """One staged entry in full: what the file said, what it is now, what it hits."""

    source: Any
    draft: Any
    duplicate: Optional[DuplicateRecipe] = None


class BatchDetail(BaseModel):
    """A staged batch and its items. State is derived, never stored."""

    model_config = ConfigDict(extra="forbid")

    id: int
    filename: str
    created_at: datetime
    created_by_user_id: int
    counts: Dict[str, int]
    items: List[ItemSummary]


class ItemOutcome(BaseModel):
    """The result of a skip or a commit.

    ``batch_deleted`` says whether that was the last open item, because a
    finished batch is pruned and the page has to stop pointing at it.
    """

    model_config = ConfigDict(extra="forbid")

    item: ItemSummary
    batch_deleted: bool


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _title(item: models.CatalogImportItem) -> Optional[str]:
    title = (item.draft or {}).get("title") if isinstance(item.draft, dict) else None
    return title if isinstance(title, str) else None


def _problems(
    db: Session, item: models.CatalogImportItem, system: Optional[models.User] = None
) -> List[str]:
    """What still stands between this item and a recipe.

    Only asked of an item still under review: a committed or skipped one is
    finished, and reporting work left on it would be noise.
    """
    if item.state not in catalog_import.OPEN_STATES:
        return []
    return catalog_import.item_problems(db, item, system)


def _summary(
    db: Session, item: models.CatalogImportItem, system: Optional[models.User] = None
) -> ItemSummary:
    return ItemSummary(
        id=item.id,
        position=item.position,
        title=_title(item),
        state=item.state,
        error=item.error,
        problems=_problems(db, item, system),
        duplicate_recipe_id=item.duplicate_recipe_id,
        committed_recipe_id=item.committed_recipe_id,
    )


def _batch_body(db: Session, batch: models.CatalogImportBatch) -> BatchDetail:
    counts = {state: 0 for state in models.IMPORT_ITEM_STATES}
    for item in batch.items:
        counts[item.state] = counts.get(item.state, 0) + 1
    # Resolved once for the whole batch: every open item asks the same question
    # of the same account, and the router is already inside one transaction.
    system = catalog.system_user(db)
    return BatchDetail(
        id=batch.id,
        filename=batch.filename,
        created_at=batch.created_at,
        created_by_user_id=batch.created_by_user_id,
        counts=counts,
        items=[_summary(db, item, system) for item in batch.items],
    )


def _duplicate_body(db: Session, recipe_id: Optional[int]) -> Optional[DuplicateRecipe]:
    if recipe_id is None:
        return None
    recipe = db.get(models.Recipe, recipe_id)
    if recipe is None:  # ON DELETE SET NULL has not caught up, or it is gone
        return None
    return DuplicateRecipe(
        id=recipe.id,
        title=recipe.title,
        course=recipe.course,
        servings=recipe.servings,
        bulk_prep=bool(recipe.bulk_prep),
        image_url=recipe.image_url,
        procedure=recipe.procedure,
        tags=[tag.name for tag in recipe.tags],
        ingredients=list(catalog.ingredient_lines(recipe)),
    )


def _detail_body(db: Session, item: models.CatalogImportItem) -> ItemDetail:
    return ItemDetail(
        **_summary(db, item).model_dump(),
        source=item.source,
        draft=item.draft,
        duplicate=_duplicate_body(db, item.duplicate_recipe_id),
    )


def _batch_or_404(db: Session, batch_id: int) -> models.CatalogImportBatch:
    try:
        return catalog_import.get_batch(db, batch_id)
    except catalog_import.ImportBatchNotFound:
        raise HTTPException(status_code=404, detail="Not found")


def _item_or_404(db: Session, batch_id: int, item_id: int) -> models.CatalogImportItem:
    """The item, only through the batch it actually belongs to.

    The batch id in the path is part of the identity, not decoration: an item id
    borrowed from another batch is a 404, so a stale review page cannot edit
    somebody else's staging area by guessing.
    """
    _batch_or_404(db, batch_id)
    try:
        item = catalog_import.get_item(db, item_id)
    except catalog_import.ImportItemNotFound:
        raise HTTPException(status_code=404, detail="Not found")
    if item.batch_id != batch_id:
        raise HTTPException(status_code=404, detail="Not found")
    return item


def _outcome(db: Session, item: models.CatalogImportItem) -> ItemOutcome:
    """Build the body, prune the batch if it is finished, then commit.

    The body is built *before* the prune because pruning deletes the item it
    describes.
    """
    summary = _summary(db, item)
    body = ItemOutcome(
        item=summary,
        batch_deleted=catalog_import.prune_if_finished(db, item.batch),
    )
    db.commit()
    return body


# ---------------------------------------------------------------------------
# routes
# ---------------------------------------------------------------------------
@router.post("", response_model=BatchDetail, status_code=201)
@ratelimit.limiter.limit(ratelimit.CATALOG_ADMIN_RATE_LIMIT)
def upload_import(request: Request, payload: UploadRequest, db: Db,
                  admin: models.User = Depends(auth_users.require_admin)) -> BatchDetail:
    """Stage a parsed JSON file as a batch to review. Nothing reaches the catalog yet."""
    try:
        batch = catalog_import.stage_upload(db, admin, payload.filename, payload.entries)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
    body = _batch_body(db, batch)
    db.commit()
    return body


@router.get("", response_model=Optional[BatchDetail])
def get_open_import(db: Db) -> Optional[BatchDetail]:
    """The batch still under review, or ``null``. A finished batch is pruned."""
    batch = catalog_import.open_batch(db)
    return _batch_body(db, batch) if batch is not None else None


@router.get("/{batch_id}", response_model=BatchDetail)
def get_import(batch_id: int, db: Db) -> BatchDetail:
    return _batch_body(db, _batch_or_404(db, batch_id))


@router.delete("/{batch_id}", status_code=204)
@ratelimit.limiter.limit(ratelimit.CATALOG_ADMIN_RATE_LIMIT)
def abandon_import(request: Request, batch_id: int, db: Db) -> None:
    """Throw the batch away. Recipes already committed from it stay."""
    db.delete(_batch_or_404(db, batch_id))
    db.commit()


@router.get("/{batch_id}/items/{item_id}", response_model=ItemDetail)
def get_import_item(batch_id: int, item_id: int, db: Db) -> ItemDetail:
    """One item: the untouched source, the working copy, and the duplicate to compare."""
    return _detail_body(db, _item_or_404(db, batch_id, item_id))


@router.patch("/{batch_id}/items/{item_id}", response_model=ItemDetail)
@ratelimit.limiter.limit(ratelimit.CATALOG_ADMIN_RATE_LIMIT)
def update_import_item(request: Request, batch_id: int, item_id: int,
                       payload: DraftWrite, db: Db) -> ItemDetail:
    """Save the working copy.

    A draft that does not parse is not a 400: it is stored, and the item goes
    back to ``invalid`` carrying the reason, so half-finished work survives the
    admin leaving the page.
    """
    item = _item_or_404(db, batch_id, item_id)
    try:
        item = catalog_import.update_item(db, item.id, payload.draft)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
    body = _detail_body(db, item)
    db.commit()
    return body


@router.post("/{batch_id}/items/{item_id}/skip", response_model=ItemOutcome)
@ratelimit.limiter.limit(ratelimit.CATALOG_ADMIN_RATE_LIMIT)
def skip_import_item(request: Request, batch_id: int, item_id: int, db: Db) -> ItemOutcome:
    """Leave this entry out of the catalog."""
    item = _item_or_404(db, batch_id, item_id)
    try:
        item = catalog_import.skip_item(db, item.id)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
    return _outcome(db, item)


@router.post("/{batch_id}/items/{item_id}/commit", response_model=ItemOutcome)
@ratelimit.limiter.limit(ratelimit.CATALOG_ADMIN_RATE_LIMIT)
def commit_import_item(request: Request, batch_id: int, item_id: int, db: Db) -> ItemOutcome:
    """Turn the item's draft into a system-owned **draft** recipe.

    400 while anything is unresolved, listing everything outstanding rather than
    one problem at a time.
    """
    item = _item_or_404(db, batch_id, item_id)
    try:
        catalog_import.commit_item(db, item.id)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
    return _outcome(db, item)
