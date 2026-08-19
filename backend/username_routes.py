"""Identity endpoints: username availability (UN-7).

Phase 0 ships this module empty and pre-wired into ``main`` (D-6) so the Phase
1A agent can fill it without touching a contended file. It owns its own
Pydantic models rather than adding them to ``schemas.py``, which is what keeps
the parallel phases from colliding.

To be built here:

* ``GET /usernames/available?u=`` -- rate-limited via ``ratelimit.limiter`` with
  ``ratelimit.USERNAME_CHECK_RATE_LIMIT``, returning ``{available, reason}`` and
  doing the same work whether the handle is taken, reserved, or free.

Deliberately *not* built here: ``POST /auth/username``. UN-8/UN-9 are deferred
to Part 2; the ``username_changed_at`` column and the ``released`` reservation
reason ship now so that flow needs no migration.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

import ratelimit
import usernames
from database import get_db
from models import ReservedUsername

router = APIRouter(tags=["usernames"])

#: Generous enough to survive a paste with surrounding whitespace, small enough
#: that an oversized body cannot be used to amplify the work per request. The
#: real rule is ``usernames.MAX_LENGTH``; this is only the transport bound, and
#: it is enforced by FastAPI *before* the handler opens a session.
_MAX_QUERY_LENGTH = 64


class UsernameAvailability(BaseModel):
    """The whole response. Deliberately two fields and no more (UN-6).

    ``reason`` carries only why *this handle* cannot be used -- ``"taken"``,
    ``"reserved"``, or the user-facing validation message. It never names the
    account holding a handle, nor any email, id, or count: the endpoint is
    reachable unauthenticated, so anything else here would be an enumeration
    oracle rather than a form hint.
    """

    available: bool
    reason: Optional[str] = None


@router.get("/usernames/available", response_model=UsernameAvailability)
@ratelimit.limiter.limit(ratelimit.USERNAME_CHECK_RATE_LIMIT)
def check_username_available(
    request: Request,
    u: str = Query(..., max_length=_MAX_QUERY_LENGTH),
    db: Session = Depends(get_db),
) -> UsernameAvailability:
    """Whether ``u`` could be claimed right now (UN-3/UN-4/UN-6/UN-7).

    Every outcome runs exactly the same work: one
    :func:`usernames.is_available` call -- which itself issues both of its
    queries before it validates -- plus one unconditional reservation lookup
    used to phrase ``reason``. Nothing short-circuits ahead of those, so a
    caller cannot tell "taken" from "reserved" from "free" by response time.

    ``request`` is unused by the body but required: slowapi reads the
    rate-limit key off it, and omitting it fails at request time, not import
    time. The parameter is never logged -- it is arbitrary attacker-controlled
    text.
    """
    candidate = usernames.normalise(u)

    # Both facts are gathered unconditionally, in this order, for every input.
    available = usernames.is_available(db, candidate)
    reservation = db.get(ReservedUsername, candidate)
    try:
        usernames.validate(candidate)
        message = None
    except ValueError as exc:
        message = str(exc)

    if available:
        reason = None
    elif message is not None:
        reason = message
    elif reservation is not None and (
        reservation.reserved_until is None
        or reservation.reserved_until > datetime.utcnow()
    ):
        reason = "reserved"
    else:
        reason = "taken"
    return UsernameAvailability(available=available, reason=reason)
