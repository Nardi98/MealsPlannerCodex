"""The admin developer-log routes, under ``/admin/logs``.

Find an account by email or username, then download its log as JSON. Like the
other routers it only translates HTTP to :mod:`devlog` and back, never imports
``main``, and keeps its Pydantic models local.

Every route sits behind :func:`auth_users.require_admin` at the router level: a
non-admin gets 403 before any route code runs, an anonymous caller 401.
"""

from __future__ import annotations

import json
from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

import auth_users
import devlog
import models
from database import get_db

Db = Annotated[Session, Depends(get_db)]

USER_NOT_FOUND = "User not found"
SEARCH_LIMIT = 20

router = APIRouter(
    prefix="/admin/logs",
    tags=["logs-admin"],
    dependencies=[Depends(auth_users.require_admin)],
)


class LogUserOut(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: int
    email: str
    username: Optional[str]


@router.get("/users", response_model=List[LogUserOut])
def search_users(db: Db, q: str = Query(..., min_length=1)) -> List[models.User]:
    """Accounts whose email or username contains ``q``, ignoring case."""
    pattern = f"%{q.strip().lower()}%"
    stmt = (
        select(models.User)
        .where(
            or_(
                func.lower(models.User.email).like(pattern),
                func.lower(models.User.username).like(pattern),
            )
        )
        .order_by(models.User.email)
        .limit(SEARCH_LIMIT)
    )
    return list(db.execute(stmt).scalars())


@router.get("/export")
def export_log(db: Db, user_id: int, channel: Optional[str] = None) -> Response:
    """One account's log as a downloadable JSON file."""
    user = db.get(models.User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail=USER_NOT_FOUND)
    body = {
        "user": LogUserOut.model_validate(user).model_dump(),
        "channel": channel,
        "entries": devlog.export(db, user_id=user.id, channel=channel),
    }
    filename = f"devlog-user-{user.id}{'-' + channel if channel else ''}.json"
    return Response(
        content=json.dumps(body, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
