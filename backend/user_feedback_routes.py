"""The user-facing route of the feedback system: ``POST /feedback``.

Will hold the one route any signed-in user calls to file an issue, request or
idea from inside the app. Like the other routers it only translates HTTP to
:mod:`user_feedback` and back, never imports ``main``, and keeps its Pydantic
models local rather than adding them to ``schemas.py``.

Pre-wired in ``main.py`` while still empty, so the change that adds the route
does not have to touch ``main.py``.
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["feedback"])
