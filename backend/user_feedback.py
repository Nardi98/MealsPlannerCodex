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

from sqlalchemy.orm import Session

import models
import storage


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
