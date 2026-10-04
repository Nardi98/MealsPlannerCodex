"""The admin triage routes of the feedback system, under ``/admin/feedback``.

Will hold the inbox an admin works through: listing and filtering items,
opening one (and its screenshot), and editing status, priority, tags and notes.
Like the other routers it only translates HTTP to :mod:`user_feedback` and
back, never imports ``main``, and keeps its Pydantic models local.

Every route sits behind :func:`auth_users.require_admin` at the router level,
so a non-admin gets one fixed 403 before any route code runs and an anonymous
caller gets 401. Pre-wired in ``main.py`` while still empty.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

import auth_users

router = APIRouter(
    prefix="/admin/feedback",
    tags=["feedback-admin"],
    dependencies=[Depends(auth_users.require_admin)],
)
