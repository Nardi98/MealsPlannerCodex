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
``LookupError``) to 404, ``FeedbackTagNameTaken`` to 409 and any other
``ValueError`` -- a blank string, an unknown enum value, an unsupported
screenshot type -- to 4xx. Pydantic normally rejects bad input before it gets
here, so that validation is defence in depth.
"""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

import models
import storage


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
    *before* the row is added, so an unsupported content type (``ValueError``
    from ``storage``) leaves no row behind.
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


def _commit(session: Session, item):
    session.commit()
    return item


def mark_seen(session: Session, item: models.FeedbackItem, seen: bool = True) -> models.FeedbackItem:
    """Mark ``item`` read (or, with ``seen=False``, unread). Status is untouched."""
    item.seen = seen
    return _commit(session, item)


def set_status(session: Session, item: models.FeedbackItem, status: str) -> models.FeedbackItem:
    """Move ``item`` to ``status``. Never touches ``seen``: the axes are orthogonal."""
    item.status = _one_of(status, models.FEEDBACK_STATUS_VALUES, "status")
    return _commit(session, item)


def set_priority(session: Session, item: models.FeedbackItem, priority: str) -> models.FeedbackItem:
    item.priority = _one_of(priority, models.FEEDBACK_PRIORITY_VALUES, "priority")
    return _commit(session, item)


def set_notes(session: Session, item: models.FeedbackItem, notes: str | None) -> models.FeedbackItem:
    """Set the admin's private notes, stripped; ``None`` or blank clears them."""
    item.admin_notes = (notes or "").strip() or None
    return _commit(session, item)


def set_tags(session: Session, item: models.FeedbackItem, names: list[str]) -> models.FeedbackItem:
    """Replace ``item``'s tags with ``names``, creating any tag that is missing.

    Names are normalized (``models.normalize_feedback_tag_name``), so ``Mobile``
    and ``mobile `` are one tag; duplicates collapse and blank names are
    silently ignored. An empty list removes every tag from the item; the tags
    themselves are kept.
    """
    wanted = {models.normalize_feedback_tag_name(name) for name in names} - {""}
    existing = {
        tag.name: tag
        for tag in session.execute(
            select(models.FeedbackTag).where(models.FeedbackTag.name.in_(wanted))
        ).scalars()
    }
    item.tags = [existing.get(name) or models.FeedbackTag(name=name) for name in sorted(wanted)]
    # Only the join table changes, so the column's ``onupdate`` would not fire.
    item.updated_at = func.now()
    return _commit(session, item)


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
    return _commit(session, tag)


def unseen_count(session: Session) -> int:
    """How many items no admin has opened yet -- the sidebar badge."""
    return session.execute(
        select(func.count()).select_from(models.FeedbackItem).where(models.FeedbackItem.seen.is_(False))
    ).scalar_one()
