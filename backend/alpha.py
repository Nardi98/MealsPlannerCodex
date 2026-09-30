"""ALPHA-GATE: the closed-alpha signup allowlist.

Temporary scaffolding, designed above all for removal: every dependency arrow
points *into* this module. It imports only ``models``, SQLAlchemy, FastAPI's
``HTTPException`` and Pydantic, and is imported only by ``alpha_routes.py`` and
two marked call sites in ``main.py``. When the alpha ends, delete the file, the
marked lines and the table (see
``docs/superpowers/specs/2026-09-30-alpha-allowlist-design.md``).
"""

from __future__ import annotations

from datetime import datetime
from typing import NamedTuple

from fastapi import HTTPException
from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy import exists, select
from sqlalchemy.orm import Session

import models

#: The one sentence a refused signup ever sees. Says the alpha is closed and
#: nothing about whether an account exists, preserving ``/auth/register``'s
#: anti-enumeration property.
NOT_INVITED_DETAIL = (
    "Meal Planner is in a closed alpha. "
    "This email address hasn't been invited yet."
)

_EMAIL = TypeAdapter(EmailStr)


class InviteNotFound(LookupError):
    """No ``alpha_invites`` row with the requested id."""


class InviteRow(NamedTuple):
    """One invite plus whether its address has since become an account."""

    invite: models.AlphaInvite
    signed_up: bool
    signed_up_at: datetime | None


class AddResult(NamedTuple):
    """How a batch of pasted addresses was partitioned.

    ``added`` and ``skipped_duplicates`` hold normalized addresses; ``invalid``
    echoes the token as it was pasted, so the admin recognises their own typo.
    """

    added: list[str]
    skipped_duplicates: list[str]
    invalid: list[str]


def normalize(email: str) -> str:
    """The canonical stored form, shared with every other email in the app."""
    return models.normalize_email(email)


def is_valid_email(value: str) -> bool:
    """Whether ``value`` is a well-formed address. Never raises.

    Validation is per token rather than a Pydantic field because one bad
    address in a pasted list must be reported, not fatal to the batch.
    """
    try:
        _EMAIL.validate_python(value)
    except ValidationError:
        return False
    return True


def split_emails(raw: str) -> list[str]:
    """Tokens from a free-text paste, separated by newlines and/or commas.

    Blanks are dropped and addresses that normalize alike collapse to the first
    one seen, so pasting a list twice adds nothing twice.
    """
    tokens: list[str] = []
    seen: set[str] = set()
    for chunk in raw.replace(",", "\n").split("\n"):
        token = chunk.strip()
        if not token:
            continue
        key = normalize(token)
        if key in seen:
            continue
        seen.add(key)
        tokens.append(token)
    return tokens


def assert_email_allowed(session: Session, email: str) -> None:
    """Raise 403 unless ``email`` may create an account. Never writes.

    With an empty table the gate **fails open**: a fresh, wiped or
    half-migrated database must never lock every prospective user out, and
    there is no separate kill switch by decision.
    """
    listed_any = session.execute(select(exists().select_from(models.AlphaInvite)))
    if not listed_any.scalar():
        return

    match = session.execute(
        select(models.AlphaInvite.id).where(
            models.AlphaInvite.email == normalize(email)
        )
    ).first()
    if match is None:
        raise HTTPException(status_code=403, detail=NOT_INVITED_DETAIL)


def list_invites(session: Session) -> list[InviteRow]:
    """Every invite, newest first, each saying whether it has been taken up.

    ``signed_up`` is an outer join at read time, so there is no denormalized
    flag to keep in step with the accounts table.
    """
    rows = session.execute(
        select(models.AlphaInvite, models.User.created_at)
        .outerjoin(models.User, models.User.email == models.AlphaInvite.email)
        .order_by(models.AlphaInvite.created_at.desc(), models.AlphaInvite.id.desc())
    ).all()
    return [
        InviteRow(invite=invite, signed_up=created_at is not None, signed_up_at=created_at)
        for invite, created_at in rows
    ]


def add_invites(session: Session, raw: str, *, invited_by_user_id: int | None) -> AddResult:
    """Insert every valid, not-yet-listed address in ``raw``. One commit."""
    added: list[str] = []
    skipped: list[str] = []
    invalid: list[str] = []

    candidates: list[str] = []
    for token in split_emails(raw):
        if is_valid_email(token):
            candidates.append(normalize(token))
        else:
            invalid.append(token)

    wanted = list(candidates)
    already = set()
    if wanted:
        already = set(
            session.execute(
                select(models.AlphaInvite.email).where(
                    models.AlphaInvite.email.in_(wanted)
                )
            ).scalars()
        )

    for email in candidates:
        if email in already:
            skipped.append(email)
            continue
        already.add(email)
        session.add(
            models.AlphaInvite(email=email, invited_by_user_id=invited_by_user_id)
        )
        added.append(email)

    try:
        session.commit()
    except Exception:
        session.rollback()
        raise
    return AddResult(added=added, skipped_duplicates=skipped, invalid=invalid)


def _get(session: Session, invite_id: int) -> models.AlphaInvite:
    invite = session.get(models.AlphaInvite, invite_id)
    if invite is None:
        raise InviteNotFound(invite_id)
    return invite


def update_note(session: Session, invite_id: int, note: str | None) -> models.AlphaInvite:
    """Set the admin's own reminder. The email is never editable: delete and
    re-add instead, so ``created_at`` stays an honest record."""
    invite = _get(session, invite_id)
    stripped = (note or "").strip()
    invite.note = stripped or None
    session.commit()
    return invite


def delete_invite(session: Session, invite_id: int) -> None:
    """Remove the invite. Accounts already created are untouched."""
    invite = _get(session, invite_id)
    session.delete(invite)
    session.commit()
