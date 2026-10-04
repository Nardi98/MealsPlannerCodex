"""The user-facing route of the feedback system: ``POST /feedback``.

The one route any signed-in user calls to file an issue, request or idea from
inside the app. There is deliberately no list or read route for users: what
they get back is the ``FB-<id>`` handle, nothing more. Like the other routers it
only translates HTTP to :mod:`user_feedback` and back, never imports ``main``,
and keeps its Pydantic models local rather than adding them to ``schemas.py``.
"""

from __future__ import annotations

from typing import Annotated, Literal, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

import auth_users
import models
import ratelimit
import storage
import user_feedback
from database import get_db

router = APIRouter(tags=["feedback"])

Db = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[models.User, Depends(auth_users.get_current_user)]

# At least one non-whitespace character: a blank title or body is a 422 here,
# at the HTTP layer, so the only ``ValueError`` left for the service to raise
# is the screenshot's content type (see the handler).
_NOT_BLANK = r"\S"

# Upper bounds on what one row can hold. Generous for honest use; they cap what
# a scripted caller can store per submission. The user types title and body, so
# going over is a 422 they can fix. The context fields are captured silently by
# the client, so they are clamped instead (see ``_clamp_context``): rejecting
# them would lose a report over a value the user never saw.
TITLE_MAX = 200
BODY_MAX = 10_000
CONTEXT_MAX = 500  # page_path, user_agent: truncated to this
VIEWPORT_MAX = 100_000  # keeps the value inside a Postgres INTEGER; outside -> null

# Built from the model's tuple so the allowed set has one source; subscripting
# ``Literal`` with a tuple unpacks it at runtime (static checkers object).
FeedbackType = Literal[models.FEEDBACK_TYPE_VALUES]  # type: ignore[valid-type]


def _clamp_context(
    page_path: str | None, user_agent: str | None, viewport_width: int | None
) -> tuple[str | None, str | None, int | None]:
    """Bound the silently captured context instead of rejecting it."""
    if viewport_width is not None and not 0 <= viewport_width <= VIEWPORT_MAX:
        viewport_width = None
    return (
        page_path[:CONTEXT_MAX] if page_path is not None else None,
        user_agent[:CONTEXT_MAX] if user_agent is not None else None,
        viewport_width,
    )


class FeedbackSubmitted(BaseModel):
    """The whole response: the handle the user can quote back to us."""

    model_config = ConfigDict(extra="forbid")

    ref_code: str


@router.post("/feedback", response_model=FeedbackSubmitted, status_code=201)
@ratelimit.limiter.limit(ratelimit.FEEDBACK_RATE_LIMIT)
async def submit_feedback(
    request: Request,
    db: Db,
    current_user: CurrentUser,
    title: Annotated[str, Form(max_length=TITLE_MAX, pattern=_NOT_BLANK)],
    body: Annotated[str, Form(max_length=BODY_MAX, pattern=_NOT_BLANK)],
    type: Annotated[FeedbackType, Form()],
    page_path: Annotated[Optional[str], Form()] = None,
    user_agent: Annotated[Optional[str], Form()] = None,
    viewport_width: Annotated[Optional[int], Form()] = None,
    screenshot: Annotated[Optional[UploadFile], File()] = None,
) -> FeedbackSubmitted:
    """File one feedback item as the caller and return its ``FB-<id>``.

    ``request`` is unused by the body and required by slowapi, which reads the
    rate-limit key off it.
    """
    page_path, user_agent, viewport_width = _clamp_context(page_path, user_agent, viewport_width)
    image = None
    if screenshot is not None:
        # Bounded read: one byte past the cap is enough to know it is too big,
        # without buffering an arbitrarily large upload.
        data = await screenshot.read(storage.MAX_IMAGE_BYTES + 1)
        if len(data) > storage.MAX_IMAGE_BYTES:
            raise HTTPException(status_code=413, detail="Image exceeds the 5 MB limit")
        # An empty file part (a form posted with no file chosen) is no screenshot.
        if data:
            image = (data, screenshot.content_type or "")
    try:
        # Async for the upload read; the DB write and the (possibly S3) image
        # save are blocking, so they run off the event loop.
        item = await run_in_threadpool(
            user_feedback.submit,
            db,
            current_user,
            title=title,
            body=body,
            type=type,
            page_path=page_path,
            user_agent=user_agent,
            viewport_width=viewport_width,
            screenshot=image,
        )
    except ValueError:
        # The text fields were validated above, so this can only be the
        # screenshot's content type; the service stores the image before adding
        # the row, so nothing was written. 400 per the feedback design, where
        # the recipe image upload answers the same case with 415.
        raise HTTPException(status_code=400, detail="Unsupported image type")
    return FeedbackSubmitted(ref_code=item.ref_code)
