"""Share, Shared-with-me, and Copy endpoints (§5.1, §5.2, §5.3, §7).

Phase 0 ships this module empty and pre-wired into ``main`` (D-6); the Phase 2A
agent owns its contents and defines its request/response models locally.

To be built here:

* ``POST /recipes/{id}/shares`` -- SH-1/4/5/9, rate-limited per user (SH-11 via
  ``ratelimit.SHARE_RATE_LIMIT``), promoting a private recipe to ``unlisted``
  (VIS-6).
* ``GET /recipes/{id}/shares`` (SH-20, owner only) and
  ``DELETE /shares/{share_id}`` (revoke, then demote per VIS-7).
* ``GET /shared-with-me`` (SWM-1/2/4/5) and the dismiss endpoint (SWM-3).
* ``POST /s/{token}/copy`` -- CP-1..CP-11 plus the AT-1 attribution snapshot.

The sharpest trap waiting here is CP-3: ``crud.get_or_create_ingredient``
resolves by id *before* name, so the copy path must pass ``ingredient_id=None``
or it will bind the copy to the source owner's ingredient rows.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy.orm import Session

import auth_users
import models
import ratelimit
import shares
from database import get_db

router = APIRouter(tags=["shares"])

Db = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[models.User, Depends(auth_users.get_current_user)]

#: SH-22: revoked, expired, and never-existed must be indistinguishable, and the
#: owner-scoped routes must not confirm that another account's row exists
#: either. One literal, used everywhere, so the bodies cannot drift apart.
NOT_FOUND = "Not found"


def _not_found() -> HTTPException:
    return HTTPException(status_code=404, detail=NOT_FOUND)


# ---------------------------------------------------------------------------
# models (kept local to this router per D-6)
# ---------------------------------------------------------------------------
class ShareIn(BaseModel):
    """What the sharer chooses (SH-4, SH-5, SH-9).

    Only an email may name a recipient. Resolving a typed address to an account
    at creation time is what PRV-7 forbids leaking, and the cheapest way not to
    leak it is not to look it up: membership of the recipient's Shared-with-me
    is decided later, by matching their *verified* address.
    """

    model_config = ConfigDict(extra="forbid")

    mode: Literal["link", "person"] = "link"
    recipient_email: Optional[str] = None
    expires_at: Optional[datetime] = None

    @field_validator("recipient_email")
    @classmethod
    def _canonicalise(cls, value: Optional[str]) -> Optional[str]:
        """Normalise the address the way ``User.email`` is normalised.

        Deliberately *not* ``EmailStr``: the address is never delivered to (SH-10
        is not built), it is only ever compared for equality against a stored,
        already-verified ``users.email``. Strict RFC parsing would therefore buy
        no safety while rejecting addresses that a real account can legitimately
        hold. The shape check below exists to reject obvious nonsense and to cap
        the length; matching does the rest.
        """
        if value is None:
            return None
        email = models.normalize_email(value)
        if not email:
            return None
        local, sep, domain = email.partition("@")
        if not sep or not local or not domain or len(email) > 254:
            raise ValueError("Not a valid email address")
        return email


class ShareOut(BaseModel):
    """One share as its owner sees it (SH-20).

    No token and no digest: the raw token exists once, in the creation
    response, and ``token_hash`` is an offline-guessing target with no use to a
    UI that revokes by id.
    """

    model_config = ConfigDict(extra="forbid")

    id: int
    mode: str
    recipient_email: Optional[str] = None
    created_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None
    last_viewed_at: Optional[datetime] = None
    active: bool

    @classmethod
    def from_share(cls, share: models.RecipeShare) -> "ShareOut":
        return cls(
            id=share.id,
            mode=share.mode,
            recipient_email=share.recipient_email,
            created_at=share.created_at,
            expires_at=share.expires_at,
            revoked_at=share.revoked_at,
            last_viewed_at=share.last_viewed_at,
            active=shares.is_share_active(share),
        )


class ShareCreated(ShareOut):
    """The creation response: a :class:`ShareOut` plus the one-time URL (SH-1)."""

    url: str


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _owned_recipe(db: Session, recipe_id: int, user: models.User) -> models.Recipe:
    """The caller's own recipe, or a 404 that says nothing about anyone else's."""
    recipe = db.get(models.Recipe, recipe_id)
    if recipe is None or recipe.user_id != user.id:
        raise _not_found()
    return recipe


# ---------------------------------------------------------------------------
# creation (§5.1)
# ---------------------------------------------------------------------------
@router.post(
    "/recipes/{recipe_id}/shares", response_model=ShareCreated, status_code=201
)
@ratelimit.limiter.limit(ratelimit.SHARE_RATE_LIMIT)
def create_recipe_share(
    request: Request,
    recipe_id: int,
    payload: ShareIn,
    db: Db,
    current_user: CurrentUser,
) -> ShareCreated:
    """Mint a share on the caller's own recipe and return its URL once.

    ``request`` is required by slowapi (SH-11) and is also what
    :func:`shares.share_url` falls back to when ``PUBLIC_BASE_URL`` is unset.
    """
    recipe = _owned_recipe(db, recipe_id, current_user)
    try:
        share, token = shares.create_share(
            db,
            recipe=recipe,
            owner=current_user,
            mode=payload.mode,
            recipient_email=payload.recipient_email,
            expires_at=payload.expires_at,
        )
    except PermissionError:
        # Unreachable given ``_owned_recipe``, but the domain layer owns the
        # rule and this keeps the route honest if that ever changes.
        raise _not_found()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # The domain layer only flushes; the transaction is the route's (VIS-6's
    # promotion and the share row must land together or not at all).
    url = shares.share_url(token, request)
    db.commit()
    db.refresh(share)
    return ShareCreated(**ShareOut.from_share(share).model_dump(), url=url)


# ---------------------------------------------------------------------------
# listing and revocation (§5.2)
# ---------------------------------------------------------------------------
@router.get("/recipes/{recipe_id}/shares", response_model=List[ShareOut])
def list_recipe_shares(
    recipe_id: int,
    db: Db,
    current_user: CurrentUser,
) -> List[ShareOut]:
    """Every share on the caller's recipe, newest first (SH-20).

    Revoked and expired rows are included -- the owner asked "who did I share
    this with", and hiding the withdrawn grants would answer a different
    question. ``active`` distinguishes them.
    """
    recipe = _owned_recipe(db, recipe_id, current_user)
    rows = (
        db.query(models.RecipeShare)
        .filter(models.RecipeShare.recipe_id == recipe.id)
        .order_by(
            models.RecipeShare.created_at.desc(), models.RecipeShare.id.desc()
        )
        .all()
    )
    return [ShareOut.from_share(row) for row in rows]


@router.delete("/shares/{share_id}", status_code=204)
def revoke_recipe_share(
    share_id: int,
    db: Db,
    current_user: CurrentUser,
) -> Response:
    """Revoke one share, then apply VIS-7 to the recipe it guarded.

    404 rather than 403 for someone else's share id: a 403 would confirm the
    row exists, which is a (small) enumeration oracle over other people's
    shares.
    """
    share = db.get(models.RecipeShare, share_id)
    if share is None or share.created_by_user_id != current_user.id:
        raise _not_found()

    shares.revoke_share(db, share)
    recipe = db.get(models.Recipe, share.recipe_id)
    if recipe is not None:
        shares.demote_if_no_active_shares(db, recipe)
    db.commit()
    return Response(status_code=204)
