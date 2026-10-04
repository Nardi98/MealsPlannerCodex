"""The admin triage routes of the feedback system, under ``/admin/feedback``.

The inbox an admin works through: listing and filtering items, opening one (and
its screenshot), and editing status, priority, tags and notes. Like the other
routers it only translates HTTP to :mod:`user_feedback` and back, never imports
``main``, and keeps its Pydantic models local.

Every route sits behind :func:`auth_users.require_admin` at the router level,
so a non-admin gets one fixed 403 before any route code runs -- identical
whether the id exists or not -- and an anonymous caller gets 401.

Bodies are built field by field from an explicit allowlist. ``screenshot_key``
is a storage address and never leaves the server: the page learns only
``has_screenshot`` and fetches the bytes through the screenshot route, which is
behind the same guard.

Route order matters: ``/unseen-count`` and ``/tags`` are declared before
``/{item_id}``, so they are never parsed as an id.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy.orm import Session

import auth_users
import models
import ratelimit
import storage
import user_feedback
from database import get_db

Db = Annotated[Session, Depends(get_db)]

#: The enum vocabularies, spelled from the models' tuples so there is one list.
STATUS = Literal[models.FEEDBACK_STATUS_VALUES]
PRIORITY = Literal[models.FEEDBACK_PRIORITY_VALUES]
TYPE = Literal[models.FEEDBACK_TYPE_VALUES]

ITEM_NOT_FOUND = "Feedback item not found"
TAG_NOT_FOUND = "Feedback tag not found"
SCREENSHOT_NOT_FOUND = "Screenshot not found"

router = APIRouter(
    prefix="/admin/feedback",
    tags=["feedback-admin"],
    dependencies=[Depends(auth_users.require_admin)],
)


# ---------------------------------------------------------------------------
# models (kept local to this router)
# ---------------------------------------------------------------------------
class AuthorOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    email: str
    username: Optional[str]
    display_name: Optional[str]


class FeedbackItemAdmin(BaseModel):
    """One item as the triage page reads it. No ``screenshot_key``, by design."""

    model_config = ConfigDict(extra="forbid")

    id: int
    ref_code: str
    title: str
    body: str
    type: str
    status: str
    priority: str
    seen: bool
    page_path: Optional[str]
    user_agent: Optional[str]
    viewport_width: Optional[int]
    has_screenshot: bool
    admin_notes: Optional[str]
    tags: List[str]
    author: Optional[AuthorOut]
    created_at: datetime
    updated_at: datetime


class ItemPatch(BaseModel):
    """Any subset of the triage fields.

    Every field but ``admin_notes`` is non-nullable: an explicit ``null`` is a
    422, and an omitted field is left alone (defaults are not validated, so
    ``None`` here means "not sent"). ``admin_notes`` is the one field ``null``
    is meaningful for -- it clears -- so the route tells it apart from an
    omitted one by ``model_fields_set``. The sent fields are applied in one
    ``user_feedback.update_item`` call -- one commit -- so a PATCH is never left
    half applied.
    """

    model_config = ConfigDict(extra="forbid")

    status: STATUS = None
    priority: PRIORITY = None
    admin_notes: Optional[str] = None
    tags: List[str] = None
    seen: bool = None


class TagOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    name: str


class TagRename(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str

    @field_validator("name")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("name must not be blank")
        return value


class UnseenCountOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    count: int


def _author(user: Optional[models.User]) -> Optional[AuthorOut]:
    if user is None:
        return None
    return AuthorOut(id=user.id, email=user.email, username=user.username, display_name=user.display_name)


def _item(item: models.FeedbackItem) -> FeedbackItemAdmin:
    return FeedbackItemAdmin(
        id=item.id,
        ref_code=item.ref_code,
        title=item.title,
        body=item.body,
        type=item.type,
        status=item.status,
        priority=item.priority,
        seen=item.seen,
        page_path=item.page_path,
        user_agent=item.user_agent,
        viewport_width=item.viewport_width,
        has_screenshot=item.screenshot_key is not None,
        admin_notes=item.admin_notes,
        tags=sorted(tag.name for tag in item.tags),
        author=_author(item.author),
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def _get_item(db: Session, item_id: int) -> models.FeedbackItem:
    try:
        return user_feedback.get_item(db, item_id)
    except user_feedback.FeedbackItemNotFound:
        raise HTTPException(status_code=404, detail=ITEM_NOT_FOUND)


# ---------------------------------------------------------------------------
# fixed paths first: they must not be parsed as an ``{item_id}``
# ---------------------------------------------------------------------------
@router.get("", response_model=List[FeedbackItemAdmin])
def list_feedback(
    db: Db,
    status: Optional[STATUS] = None,
    type: Optional[TYPE] = None,
    priority: Optional[PRIORITY] = None,
    tag: Optional[str] = None,
    seen: Optional[bool] = None,
) -> List[FeedbackItemAdmin]:
    """Every item matching all the given filters, newest first."""
    items = user_feedback.list_items(db, status=status, type=type, priority=priority, tag=tag, seen=seen)
    return [_item(item) for item in items]


@router.get("/unseen-count", response_model=UnseenCountOut)
def unseen_count(db: Db) -> UnseenCountOut:
    """How many items no admin has opened yet -- the sidebar badge."""
    return UnseenCountOut(count=user_feedback.unseen_count(db))


@router.get("/tags", response_model=List[TagOut])
def list_tags(db: Db) -> List[TagOut]:
    return [TagOut(id=tag.id, name=tag.name) for tag in user_feedback.list_tags(db)]


@router.patch("/tags/{tag_id}", response_model=TagOut)
@ratelimit.limiter.limit(ratelimit.FEEDBACK_ADMIN_RATE_LIMIT)
def rename_tag(request: Request, tag_id: int, payload: TagRename, db: Db) -> TagOut:
    """Rename a tag; the name is normalized, and one taken by another tag is a 409."""
    try:
        tag = user_feedback.rename_tag(db, user_feedback.get_tag(db, tag_id), payload.name)
    except user_feedback.FeedbackTagNotFound:
        raise HTTPException(status_code=404, detail=TAG_NOT_FOUND)
    except user_feedback.FeedbackTagNameTaken:
        raise HTTPException(status_code=409, detail="Another tag already has that name")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return TagOut(id=tag.id, name=tag.name)


# ---------------------------------------------------------------------------
# one item
# ---------------------------------------------------------------------------
@router.get("/{item_id}", response_model=FeedbackItemAdmin)
def get_feedback(item_id: int, db: Db) -> FeedbackItemAdmin:
    """One item. A pure read: the page marks it seen with an explicit PATCH."""
    return _item(_get_item(db, item_id))


@router.patch("/{item_id}", response_model=FeedbackItemAdmin)
@ratelimit.limiter.limit(ratelimit.FEEDBACK_ADMIN_RATE_LIMIT)
def update_feedback(request: Request, item_id: int, payload: ItemPatch, db: Db) -> FeedbackItemAdmin:
    """Apply whichever triage fields were sent; an empty body changes nothing."""
    item = _get_item(db, item_id)
    user_feedback.update_item(db, item, **{field: getattr(payload, field) for field in payload.model_fields_set})
    return _item(item)


@router.get("/{item_id}/screenshot")
def get_screenshot(item_id: int, db: Db) -> Response:
    """The attached image's bytes, with the stored content type.

    ``private, no-store``: it is admin-only content, so no shared cache may keep
    it and no browser cache should outlive the session.
    """
    item = _get_item(db, item_id)
    if item.screenshot_key is None:
        raise HTTPException(status_code=404, detail=SCREENSHOT_NOT_FOUND)
    try:
        data, content_type = storage.open_image(item.screenshot_key)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=SCREENSHOT_NOT_FOUND)
    return Response(content=data, media_type=content_type, headers={"Cache-Control": "private, no-store"})
