"""Identity endpoints: username availability (UN-7) and confirmation (D-7).

Phase 0 ships this module empty and pre-wired into ``main`` (D-6) so the Phase
1A agent can fill it without touching a contended file. It owns its own
Pydantic models rather than adding them to ``schemas.py``, which is what keeps
the parallel phases from colliding.

Built here:

* ``GET /usernames/available?u=`` -- rate-limited via ``ratelimit.limiter`` with
  ``ratelimit.USERNAME_CHECK_RATE_LIMIT``, returning ``{available, reason}`` and
  doing the same work whether the handle is taken, reserved, or free.
* ``POST /auth/username`` -- **confirm-once** handle selection.

On the second endpoint, and why the earlier "deliberately not built here" note
no longer holds: D-7 makes ``username_changed_at IS NULL`` mean
"system-assigned, unconfirmed", and the SPA's gate renders *only* the
handle-selection page while ``username_confirmed`` is false. A Google sign-up
therefore starts behind that gate, and with no endpoint able to stamp
``username_changed_at`` it could never leave -- the account was trapped. This
route is the minimum that releases it: it assigns the chosen handle and stamps
the column, once.

The deferral of UN-8/UN-9 is therefore *partial*, not cancelled. This route
refuses an account whose ``username_changed_at`` is already set, so it can
never be used to rename. Part 2 still owns the real change flow: the 30-day
cooldown (UN-8), reserving the vacated handle (UN-9), and the ``released``
reservation reason -- none of which exist here.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import auth_users
import ratelimit
import schemas
import usernames
from database import get_db
from models import ReservedUsername, User

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


class ConfirmUsernameRequest(BaseModel):
    """The submitted handle, and nothing else.

    Deliberately one field: the account being written is taken from the bearer
    token, never from the payload, so there is no id or email here for a caller
    to point at somebody else's row. Extra keys are ignored by Pydantic's
    default, which is what makes that guarantee hold rather than depend on the
    handler remembering to look away.
    """

    username: str = Field(max_length=_MAX_QUERY_LENGTH)


#: The one wording for every kind of handle unavailability, owned by
#: ``usernames`` because ``main.register`` answers with it too and two copies
#: could drift into an oracle. See the constant's own note for why "taken"
#: covers reserved handles as well.
_CONFLICT = usernames.CONFLICT_MESSAGE


@router.post("/auth/username", response_model=schemas.UserOut)
@ratelimit.limiter.limit(ratelimit.USERNAME_CHECK_RATE_LIMIT)
def confirm_username(
    request: Request,
    payload: ConfirmUsernameRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(auth_users.get_current_user),
) -> User:
    """Claim a handle once, releasing the account from the SPA gate (D-7).

    Confirm-*once*: an account whose ``username_changed_at`` is already set is
    refused with 403. That is the line that keeps UN-8/UN-9 in Part 2 -- this
    route can move an account from "unconfirmed" to "confirmed" and nowhere
    else, so it cannot be used to rename, and it never has to reserve a vacated
    handle.

    ``request`` is unused by the body but required: slowapi reads the
    rate-limit key off it. Neither it nor ``payload.username`` is logged -- the
    handle is attacker-controlled text, and it is about to become public.
    """
    if current_user.username_changed_at is not None:
        raise HTTPException(
            status_code=403, detail="Your username has already been set"
        )

    candidate = usernames.normalise(payload.username)
    try:
        usernames.validate(candidate)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # A UX affordance, not the guarantee: two concurrent callers can both pass
    # this. ``uq_user_username_lower`` decides, and the loser is caught below.
    #
    # "Already mine" has to pass too. The provisional handle sits on the
    # caller's own row, so a plain availability check calls it taken and the
    # commonest answer at the gate -- "keep the one you suggested" -- would be
    # refused, leaving the account trapped behind the gate this route exists to
    # open. The concession is narrow: it can only ever re-confirm a handle the
    # account already holds, so it grants nothing a caller did not have.
    already_mine = candidate == usernames.normalise(current_user.username or "")
    if not (already_mine or usernames.is_available(db, candidate)):
        raise HTTPException(status_code=409, detail=_CONFLICT)

    try:
        # A SAVEPOINT rather than a bare flush: a lost race must roll back the
        # failed assignment *only*, leaving the session usable so the caller
        # can simply retry with another handle.
        with db.begin_nested():
            current_user.username = candidate
            current_user.username_changed_at = datetime.utcnow()
            db.flush()
    except IntegrityError:
        # Somebody claimed it between the check and the flush. Same 409 as any
        # other conflict -- never a 500, and never a hint that it was a race.
        db.expire(current_user)
        raise HTTPException(status_code=409, detail=_CONFLICT)

    db.commit()
    db.refresh(current_user)
    return current_user
