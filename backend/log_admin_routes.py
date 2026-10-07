"""The admin developer-log routes, under ``/admin/logs``.

Find an account by email or username, then fetch its log for the page to save as JSON. Like the
other routers it only translates HTTP to :mod:`devlog` and back, never imports
``main``, and keeps its Pydantic models local.

Every route sits behind :func:`auth_users.require_admin` at the router level: a
non-admin gets 403 before any route code runs, an anonymous caller 401.
"""

from __future__ import annotations

from typing import Annotated, Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

import auth_users
import devlog
import models
from catalog import escape_like
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


class LogExportOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user: LogUserOut
    channel: Optional[str]
    entries: List[Dict[str, Any]]


@router.get("/users", response_model=List[LogUserOut])
def search_users(db: Db, q: str = Query(..., min_length=1)) -> List[models.User]:
    """Accounts whose email or username contains ``q``, ignoring case."""
    pattern = f"%{escape_like(q.strip())}%"
    stmt = (
        select(models.User)
        .where(
            or_(
                models.User.email.ilike(pattern, escape="\\"),
                models.User.username.ilike(pattern, escape="\\"),
            )
        )
        .order_by(models.User.email)
        .limit(SEARCH_LIMIT)
    )
    return list(db.execute(stmt).scalars())


@router.get("/export", response_model=LogExportOut)
def export_log(db: Db, user_id: int, channel: Optional[str] = None) -> Dict[str, Any]:
    """One account's log; the page saves it as a file."""
    user = db.get(models.User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail=USER_NOT_FOUND)
    return {
        "user": user,
        "channel": channel,
        "entries": devlog.export(db, user_id=user.id, channel=channel),
    }
