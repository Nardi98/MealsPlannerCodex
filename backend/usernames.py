"""Username normalisation, validation, and reservation (§8).

Pure logic with no routes: the availability endpoint (UN-7) lives in
``username_routes.py``, and the change flow (UN-8/UN-9) is deferred to Part 2.
Keeping the rules here means the registration path, the seed scripts, and the
future endpoint all enforce one definition of a valid handle.

Note that :func:`is_available` is *not* the uniqueness guarantee -- that is
``uq_user_username_lower`` on ``users`` (UN-2). This module answers "would this
be accepted?" for a form; the database answers "was it?" under concurrency.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models import RESERVED_USERNAMES, ReservedUsername, User

MIN_LENGTH = 3
MAX_LENGTH = 30

#: UN-3, as one expression: lowercase alphanumerics and underscores, 3-30 long,
#: never starting or ending with an underscore, never two in a row.
_PATTERN = re.compile(r"^[a-z0-9]+(?:_[a-z0-9]+)*$")

#: The single wording for every way a handle can be unavailable: taken,
#: reserved, or lost in a check-then-insert race. Owned here because three
#: modules answer with it -- ``main.register``, ``username_routes.confirm_username``
#: and the race handler behind both -- and a comment saying "keep these in sync"
#: is not a mechanism. If two of them drifted, the difference between the
#: messages would itself be an oracle: it would tell a caller *which* kind of
#: unavailability they hit, and "somebody claimed this a millisecond ago" is
#: not something they need to know. One constant makes that impossible rather
#: than merely discouraged.
#:
#: "Taken" is deliberately used for reserved handles too. ``GET
#: /usernames/available`` is the endpoint that exposes the distinction, and it
#: is rate-limited and about a handle the caller already typed; repeating it
#: here would hand an authenticated caller a map of the structurally blocked
#: handle space for no gain, since their next action is the same either way.
CONFLICT_MESSAGE = "That username is taken"

__all__ = [
    "MIN_LENGTH",
    "MAX_LENGTH",
    "CONFLICT_MESSAGE",
    "normalise",
    "validate",
    "is_available",
    "reserve",
    "seed_reserved",
]


def normalise(value: Optional[str]) -> str:
    """Return ``value`` folded to the canonical stored form.

    Trimming and lowercasing only: normalisation never *repairs* a handle, so a
    name containing a dash is normalised to itself and then rejected by
    :func:`validate` with a message the user can act on.
    """
    if not value:
        return ""
    return value.strip().lower()


def validate(value: str) -> str:
    """Return ``value`` unchanged, or raise ``ValueError`` explaining why not.

    The messages are user-facing (UN-5 shows them on the registration form), so
    they name the rule that was broken rather than echoing the regex.
    """
    if not value:
        raise ValueError("Choose a username")
    if len(value) < MIN_LENGTH:
        raise ValueError(f"Usernames must be at least {MIN_LENGTH} characters")
    if len(value) > MAX_LENGTH:
        raise ValueError(f"Usernames must be at most {MAX_LENGTH} characters")
    if value.startswith("_") or value.endswith("_"):
        raise ValueError("Usernames cannot start or end with an underscore")
    if "__" in value:
        raise ValueError("Usernames cannot contain two underscores in a row")
    if not _PATTERN.match(value):
        raise ValueError(
            "Usernames can only use lowercase letters, numbers, and underscores"
        )
    return value


def _reservation_holds(row: ReservedUsername, now: datetime) -> bool:
    """Whether ``row`` still blocks the handle. ``NULL`` means permanent."""
    return row.reserved_until is None or row.reserved_until > now


def is_available(session: Session, value: str, *, now: datetime | None = None) -> bool:
    """Whether ``value`` could be claimed right now.

    Checks the reserved table (honouring an expired ``reserved_until``) and the
    ``users`` table case-insensitively. An invalid handle is reported
    unavailable rather than raising: a caller asking "is this free?" about
    ``chef!`` wants a ``False``, and the validation message comes from
    :func:`validate` on submit.

    Both branches run the same two queries regardless of the outcome, so the
    endpoint built on this cannot be used to distinguish "taken" from
    "reserved" by response time (UN-7).
    """
    now = now or datetime.utcnow()
    candidate = normalise(value)

    reservation = session.get(ReservedUsername, candidate)
    taken = session.execute(
        select(User.id).where(func.lower(User.username) == candidate).limit(1)
    ).first()

    try:
        validate(candidate)
    except ValueError:
        return False
    if reservation is not None and _reservation_holds(reservation, now):
        return False
    return taken is None


def reserve(
    session: Session,
    value: str,
    *,
    reason: str = "system",
    reserved_until: datetime | None = None,
) -> ReservedUsername:
    """Reserve ``value``, or return the existing reservation unchanged.

    Idempotent so the startup seed can run on every boot. An existing row is
    left alone rather than overwritten: a permanent ``system`` reservation must
    not be downgraded to a 30-day ``released`` one by a later call.
    """
    candidate = normalise(value)
    existing = session.get(ReservedUsername, candidate)
    if existing is not None:
        return existing

    row = ReservedUsername(
        username=candidate, reason=reason, reserved_until=reserved_until
    )
    session.add(row)
    session.flush()
    return row


def seed_reserved(session: Session) -> int:
    """Insert the UN-4 list as permanent reservations. Returns rows added.

    Called from ``main``'s startup block, so a fresh database has the list
    before the first registration can claim ``admin``.
    """
    added = 0
    for name in RESERVED_USERNAMES:
        if session.get(ReservedUsername, normalise(name)) is None:
            reserve(session, name, reason="system")
            added += 1
    return added
