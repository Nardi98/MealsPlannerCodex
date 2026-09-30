"""ALPHA-GATE: the admin routes behind the closed-alpha allowlist page.

Temporary scaffolding, deleted whole when the alpha ends (see
``docs/superpowers/specs/2026-09-30-alpha-allowlist-design.md``). Like the other
routers it only translates HTTP to :mod:`alpha` and back, and it never imports
``main``: the dependency arrows point *into* the feature, so removing it is one
file plus three marked lines.

Every route sits behind :func:`auth_users.require_admin` at the router level, so
a non-admin gets one fixed 403 before any route code runs -- identical whether
the invite id exists or not -- and an anonymous caller gets 401. Bodies are built
field by field from an explicit allowlist: ``invited_by_user_id`` is recorded but
never published, since who invited whom is nobody's business but the database's.
Pydantic models are local to this router rather than added to ``schemas.py``,
following ``catalog_admin_routes``, which also keeps the removal to one file.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

import alpha
import auth_users
import models
from database import get_db

Db = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[models.User, Depends(auth_users.get_current_user)]

router = APIRouter(
    prefix="/admin/alpha",
    tags=["alpha"],
    dependencies=[Depends(auth_users.require_admin)],
)


class InviteOut(BaseModel):
    """One invite as the admin page reads it. No inviter, by design."""

    model_config = ConfigDict(extra="forbid")

    id: int
    email: str
    note: Optional[str]
    created_at: datetime
    signed_up: bool
    signed_up_at: Optional[datetime]


class InvitesIn(BaseModel):
    """A paste of addresses: newline- and/or comma-separated free text.

    One free-text field rather than a list, because the admin's source is a
    pasted list and partitioning it is the service's job -- a malformed address
    must be *reported* alongside the ones that worked, not reject the batch.
    """

    model_config = ConfigDict(extra="forbid")

    emails: str


class NoteIn(BaseModel):
    """The admin's own reminder. ``extra="forbid"`` refuses ``email``: an
    address is never edited in place, so ``created_at`` stays honest."""

    model_config = ConfigDict(extra="forbid")

    note: Optional[str]


class AddResultOut(BaseModel):
    """How the paste was partitioned, in the service's own three buckets."""

    model_config = ConfigDict(extra="forbid")

    added: List[str]
    skipped_duplicates: List[str]
    invalid: List[str]


NOT_FOUND = "Invite not found"


def _row(entry: alpha.InviteRow) -> InviteOut:
    return InviteOut(
        id=entry.invite.id,
        email=entry.invite.email,
        note=entry.invite.note,
        created_at=entry.invite.created_at,
        signed_up=entry.signed_up,
        signed_up_at=entry.signed_up_at,
    )


def _reload(db: Session, invite_id: int) -> InviteOut:
    """The one invite, read back through ``list_invites``.

    Going through the list keeps ``signed_up`` derived in exactly one place: a
    second query joining ``users`` here would be a second definition of what
    "signed up" means, free to drift from the one the table is rendered with.
    """
    for entry in alpha.list_invites(db):
        if entry.invite.id == invite_id:
            return _row(entry)
    raise HTTPException(status_code=404, detail=NOT_FOUND)


@router.get("/invites", response_model=List[InviteOut])
def list_invites(db: Db) -> List[InviteOut]:
    """Every invited address, newest first, each saying whether it was taken up."""
    return [_row(entry) for entry in alpha.list_invites(db)]


@router.post("/invites", response_model=AddResultOut)
def add_invites(payload: InvitesIn, db: Db, current_user: CurrentUser) -> AddResultOut:
    """Invite everything valid and not already listed in the pasted text."""
    result = alpha.add_invites(
        db, payload.emails, invited_by_user_id=current_user.id
    )
    # The buckets are the service's own; ``extra="forbid"`` still pins the names.
    return AddResultOut(**result._asdict())


@router.patch("/invites/{invite_id}", response_model=InviteOut)
def update_invite_note(invite_id: int, payload: NoteIn, db: Db) -> InviteOut:
    """Set or clear the note. The address itself is immutable."""
    try:
        alpha.update_note(db, invite_id, payload.note)
    except alpha.InviteNotFound:
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    return _reload(db, invite_id)


@router.delete("/invites/{invite_id}", status_code=204)
def delete_invite(invite_id: int, db: Db) -> None:
    """Withdraw an invite. An account already created with it is untouched."""
    try:
        alpha.delete_invite(db, invite_id)
    except alpha.InviteNotFound:
        raise HTTPException(status_code=404, detail=NOT_FOUND)
