"""Domain logic of the user feedback system: filing, listing and triaging items.

A pure domain module, called by ``user_feedback_routes`` (a user's one
submission route) and ``user_feedback_admin_routes`` (admin triage). It imports
nothing of ours but ``models`` and ``storage`` -- never ``main``, a router,
``crud`` or ``scoping`` (guarded by ``tests/test_architecture_guards.py``).

Feedback is **not owner-scoped, by design**: ``FeedbackItem.user_id`` records
who filed an item (provenance), not who owns it, and the only reader is an admin
who must see every row. Queries here are therefore deliberately not passed
through ``scoping.scope()``.

Named ``user_feedback`` because "feedback" already means the meal-plan
accept/reject signal.

Every function takes the session first and commits its own work. The routers
translate the errors: ``FeedbackItemNotFound`` / ``FeedbackTagNotFound`` (both
``LookupError``) to 404, ``FeedbackTagNameTaken`` to 409 and
``storage.UnsupportedImageType`` to 400. Every other ``ValueError`` raised here
-- a blank string, an unknown enum value -- is defence in depth: the routers'
Pydantic models reject that input before it gets here.
"""

from __future__ import annotations

from typing import Any, Literal
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

import models
import storage


# The enum vocabularies as types, for the routers' Pydantic models, built from
# the models' tuples so the allowed sets have one source. Subscripting
# ``Literal`` with a tuple unpacks it at runtime; static checkers object.
FeedbackType = Literal[models.FEEDBACK_TYPE_VALUES]  # type: ignore[valid-type]
FeedbackStatus = Literal[models.FEEDBACK_STATUS_VALUES]  # type: ignore[valid-type]
FeedbackPriority = Literal[models.FEEDBACK_PRIORITY_VALUES]  # type: ignore[valid-type]


class FeedbackItemNotFound(LookupError):
    """No ``feedback_items`` row with the requested id."""


class FeedbackTagNotFound(LookupError):
    """No ``feedback_tags`` row with the requested id."""


class FeedbackTagNameTaken(Exception):
    """A rename's normalized name already belongs to another tag (a 409).

    Deliberately *not* a ``ValueError``: a router mapping ``ValueError`` to 422
    must not swallow this conflict by catching the broader class first.
    """


def _required_text(value: str | None, field: str) -> str:
    stripped = (value or "").strip()
    if not stripped:
        raise ValueError(f"{field} must not be blank")
    return stripped


def _one_of(value: str, allowed: tuple[str, ...], field: str) -> str:
    if value not in allowed:
        raise ValueError(f"unknown {field} {value!r}; expected one of {', '.join(allowed)}")
    return value


def submit(
    session: Session,
    user: models.User | None,
    title: str,
    body: str,
    type: str,
    page_path: str | None = None,
    user_agent: str | None = None,
    viewport_width: int | None = None,
    screenshot: tuple[bytes, str] | None = None,
) -> models.FeedbackItem:
    """File one item and return it, committed, with its ``FB-<id>`` ref code.

    ``screenshot`` is ``None`` or a ``(data, content_type)`` pair. It is stored
    *before* the row is added, so an unsupported content type
    (``storage.UnsupportedImageType``) leaves no row behind.
    """
    title = _required_text(title, "title")
    body = _required_text(body, "body")
    _one_of(type, models.FEEDBACK_TYPE_VALUES, "type")

    screenshot_key = None
    if screenshot is not None:
        data, content_type = screenshot
        screenshot_key = storage.save_image(data, content_type, prefix="feedback")

    item = models.FeedbackItem(
        # A unique placeholder satisfies NOT NULL / UNIQUE until the flush below
        # assigns the id; the real code replaces it before the single commit.
        ref_code=f"pending-{uuid4().hex}",
        title=title,
        body=body,
        type=type,
        user_id=user.id if user is not None else None,
        page_path=page_path,
        user_agent=user_agent,
        viewport_width=viewport_width,
        screenshot_key=screenshot_key,
    )
    session.add(item)
    try:
        session.flush()
        item.ref_code = f"FB-{item.id}"
        session.commit()
    except Exception:
        session.rollback()
        raise
    return item


def list_items(
    session: Session,
    *,
    status: str | None = None,
    type: str | None = None,
    priority: str | None = None,
    tag: str | None = None,
    seen: bool | None = None,
) -> list[models.FeedbackItem]:
    """Every item matching all the given filters, newest first (ties by id).

    ``tag`` is a name, normalized before matching. Tags and author are loaded
    up front, since the inbox serialises both for every row.
    """
    Item = models.FeedbackItem
    query = select(Item).options(selectinload(Item.tags), selectinload(Item.author))
    for column, value in ((Item.status, status), (Item.type, type), (Item.priority, priority), (Item.seen, seen)):
        if value is not None:
            query = query.where(column == value)
    if tag is not None:
        query = query.where(
            Item.tags.any(models.FeedbackTag.name == models.normalize_feedback_tag_name(tag))
        )
    return list(session.execute(query.order_by(Item.created_at.desc(), Item.id.desc())).scalars())


def get_item(session: Session, item_id: int) -> models.FeedbackItem:
    """The item with ``item_id``; raises ``FeedbackItemNotFound`` if none."""
    item = session.get(models.FeedbackItem, item_id)
    if item is None:
        raise FeedbackItemNotFound(item_id)
    return item


# Marks an ``update_item`` field as "not passed": ``None`` is a real value for
# ``admin_notes`` (it clears them), so it cannot double as "leave alone".
_UNSET: Any = object()


def update_item(
    session: Session,
    item: models.FeedbackItem,
    *,
    status: str = _UNSET,
    priority: str = _UNSET,
    admin_notes: str | None = _UNSET,
    tags: list[str] = _UNSET,
    seen: bool = _UNSET,
) -> models.FeedbackItem:
    """Apply whichever triage fields are passed to ``item``, in one commit.

    Every value is validated before anything is mutated, so a bad one raises
    ``ValueError`` with ``item`` untouched: an edit is applied whole or not at
    all. ``seen`` and ``status`` are orthogonal -- neither implies the other.

    ``admin_notes`` is stripped, and ``None`` or blank clears them. ``tags``
    replaces the item's tags, creating any that are missing: names are
    normalized (``models.normalize_feedback_tag_name``), so ``Mobile`` and
    ``mobile `` are one tag; duplicates collapse and blank names are silently
    ignored. An empty list removes every tag from the item; the tags
    themselves are kept.
    """
    changes: dict[str, Any] = {}
    if status is not _UNSET:
        changes["status"] = _one_of(status, models.FEEDBACK_STATUS_VALUES, "status")
    if priority is not _UNSET:
        changes["priority"] = _one_of(priority, models.FEEDBACK_PRIORITY_VALUES, "priority")
    if admin_notes is not _UNSET:
        changes["admin_notes"] = (admin_notes or "").strip() or None
    if seen is not _UNSET:
        changes["seen"] = seen
    if tags is not _UNSET:
        wanted = {models.normalize_feedback_tag_name(name) for name in tags} - {""}
        existing = {
            tag.name: tag
            for tag in session.execute(
                select(models.FeedbackTag).where(models.FeedbackTag.name.in_(wanted))
            ).scalars()
        }
        changes["tags"] = [existing.get(name) or models.FeedbackTag(name=name) for name in sorted(wanted)]
        # Only the join table changes, so the column's ``onupdate`` would not fire.
        changes["updated_at"] = func.now()

    for field, value in changes.items():
        setattr(item, field, value)
    session.commit()
    return item


def mark_seen(session: Session, item: models.FeedbackItem, seen: bool = True) -> models.FeedbackItem:
    """Mark ``item`` read (or, with ``seen=False``, unread). Status is untouched."""
    return update_item(session, item, seen=seen)


def set_status(session: Session, item: models.FeedbackItem, status: str) -> models.FeedbackItem:
    """Move ``item`` to ``status``. Never touches ``seen``: the axes are orthogonal."""
    return update_item(session, item, status=status)


def set_priority(session: Session, item: models.FeedbackItem, priority: str) -> models.FeedbackItem:
    return update_item(session, item, priority=priority)


def set_notes(session: Session, item: models.FeedbackItem, notes: str | None) -> models.FeedbackItem:
    """Set the admin's private notes, stripped; ``None`` or blank clears them."""
    return update_item(session, item, admin_notes=notes)


def set_tags(session: Session, item: models.FeedbackItem, names: list[str]) -> models.FeedbackItem:
    """Replace ``item``'s tags with ``names``; see ``update_item`` for the rules."""
    return update_item(session, item, tags=names)


def list_tags(session: Session) -> list[models.FeedbackTag]:
    """Every tag, sorted by name."""
    return list(session.execute(select(models.FeedbackTag).order_by(models.FeedbackTag.name)).scalars())


def get_tag(session: Session, tag_id: int) -> models.FeedbackTag:
    """The tag with ``tag_id``; raises ``FeedbackTagNotFound`` if none."""
    tag = session.get(models.FeedbackTag, tag_id)
    if tag is None:
        raise FeedbackTagNotFound(tag_id)
    return tag


def rename_tag(session: Session, tag: models.FeedbackTag, name: str) -> models.FeedbackTag:
    """Rename ``tag`` to the normalized ``name``.

    Raises ``ValueError`` for a blank name and ``FeedbackTagNameTaken`` when
    another tag already has it; renaming a tag to its own name is a no-op.
    """
    normalized = _required_text(models.normalize_feedback_tag_name(name or ""), "name")
    clash = session.execute(
        select(models.FeedbackTag.id).where(
            models.FeedbackTag.name == normalized, models.FeedbackTag.id != tag.id
        )
    ).first()
    if clash is not None:
        raise FeedbackTagNameTaken(normalized)
    tag.name = normalized
    session.commit()
    return tag


def unseen_count(session: Session) -> int:
    """How many items no admin has opened yet -- the sidebar badge."""
    return session.execute(
        select(func.count()).select_from(models.FeedbackItem).where(models.FeedbackItem.seen.is_(False))
    ).scalar_one()
