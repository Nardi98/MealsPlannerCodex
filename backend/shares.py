"""Share-token domain logic: the capability that guards private recipes.

This module is the whole security boundary of recipe sharing. A share token is
a bearer capability -- possession is authorisation -- so everything here is
written around three properties: the token is unguessable, the database never
holds a usable copy of it, and a lookup tells an attacker nothing beyond
"valid" or "not valid".

Why SHA-256 and not bcrypt/argon2 (D-5, SH-3, SH-27)
----------------------------------------------------
A password hash is deliberately slow *and* salted per row, which means the
digest cannot be indexed: resolving a token would degrade to an O(n) scan
comparing every row, and that scan's duration varies with where (and whether)
the token is found -- a timing oracle for enumeration, which is exactly what
SH-27 forbids. Slow hashing exists to make *guessing a low-entropy secret*
expensive. A share token is 256 bits from ``secrets.token_urlsafe(32)``: it has
no preimage worth guessing and no dictionary to grind. So the correct primitive
is a *fast* hash with a unique index, giving one constant-cost equality lookup.
Please do not "fix" this into bcrypt.

Timezone convention
-------------------
``recipe_shares.created_at`` / ``expires_at`` / ``revoked_at`` are naive
``DateTime`` columns, as is the rest of this codebase. Every naive value here is
interpreted as **UTC**, and every timestamp this module writes comes from
``datetime.utcnow()``. Callers passing an aware datetime get it converted to
naive UTC before comparison, so a tz-aware ``expires_at`` from an API layer
cannot silently compare wrong (or raise).
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import os
import re
import secrets
from datetime import datetime, timezone
from urllib.parse import quote

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

import models
from models import Recipe, RecipeShare, User

logger = logging.getLogger(__name__)


class HandleNotConfirmed(Exception):
    """The sharer has not chosen a username yet (UN-11, D-7).

    A named error rather than ``PermissionError``: the two failures next to it
    in :func:`create_share` need different answers. Not owning the recipe must
    disclose nothing (404); this one is about the *caller's own* account, so
    naming the missing step is both safe and the only useful thing to say.
    """


__all__ = [
    "HandleNotConfirmed",
    "mint_token",
    "hash_token",
    "resolve",
    "share_url",
    "create_share",
    "revoke_share",
    "demote_if_no_active_shares",
    "effective_visibility",
    "active_shares_for_recipient",
    "is_share_active",
    "SHARE_PATH_PREFIX",
]

#: Path the share link points at. The reverse proxy must forward ``/s/*`` to
#: the backend (Q-1's deploy-time prerequisite).
SHARE_PATH_PREFIX = "/s/"

#: A conservative ``Host`` header: hostname (or IPv6 literal) plus optional
#: port. Anything else is refused rather than spliced into a URL we hand a user.
_HOST_RE = re.compile(
    r"^(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)*"
    r"|\[[0-9A-Fa-f:.]+\])"
    r"(?::\d{1,5})?$"
)

_warned_about_host_fallback = False


# ---------------------------------------------------------------------------
# tokens
# ---------------------------------------------------------------------------
def mint_token() -> str:
    """Return a fresh 256-bit URL-safe share token (SH-2).

    ``secrets`` only -- never ``random`` (seeded, predictable) and never
    ``uuid4`` (128 bits, and version/variant bits are fixed).
    """
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """Return the SHA-256 hex digest stored in ``RecipeShare.token_hash``."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _load_share_by_hash(session: Session, digest: str) -> RecipeShare | None:
    """One indexed equality lookup. No validity predicate in the ``WHERE``.

    Kept as a seam so tests can observe that resolution performs exactly one
    query and never loads the recipe of a share it rejects.
    """
    return session.execute(
        select(RecipeShare).where(RecipeShare.token_hash == digest)
    ).scalars().first()


def resolve(session: Session, token: str) -> RecipeShare | None:
    """Return the active share for ``token``, or ``None``.

    ``None`` is the *single* outcome for all three failure modes -- revoked,
    expired, and never-existed (SH-22). There is deliberately no exception
    hierarchy and no reason code: the caller cannot distinguish them, so it
    cannot leak the distinction. The recipe is never loaded for a share that
    fails validation, so an invalid token cannot leak recipe data either.

    Validity is evaluated in Python *after* the fetch, so a hit-but-invalid
    token costs the same one indexed lookup as a hit-and-valid one (SH-27).
    """
    if not isinstance(token, str) or not token:
        # Still cheap and uniform: there is no row to find for a non-token.
        return None

    digest = hash_token(token)
    share = _load_share_by_hash(session, digest)
    if share is None:
        return None

    # Both branches below run for every hit, so the work is the same shape
    # whatever the answer.
    digest_matches = hmac.compare_digest(share.token_hash, digest)
    still_valid = is_share_active(share)
    if digest_matches and still_valid:
        return share
    return None


# ---------------------------------------------------------------------------
# validity
# ---------------------------------------------------------------------------
def _as_naive_utc(value: datetime | None) -> datetime | None:
    if value is None or value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def is_share_active(share: RecipeShare, *, now: datetime | None = None) -> bool:
    """Whether ``share`` currently grants access.

    SH-21: an expired share is treated exactly as a revoked one -- there is one
    notion of "inactive" and both feed it.
    """
    moment = _as_naive_utc(now) or datetime.utcnow()
    if _as_naive_utc(share.revoked_at) is not None:
        return False
    expires_at = _as_naive_utc(share.expires_at)
    if expires_at is not None and expires_at <= moment:
        return False
    return True


# ---------------------------------------------------------------------------
# creation
# ---------------------------------------------------------------------------
def create_share(
    session: Session,
    *,
    recipe: Recipe,
    owner: User,
    mode: str,
    recipient_user: User | None = None,
    recipient_email: str | None = None,
    expires_at: datetime | None = None,
) -> tuple[RecipeShare, str]:
    """Mint a share on ``recipe`` and return ``(share, raw_token)``.

    The raw token is returned *once* and never persisted; the caller is the only
    thing that ever sees it again.

    Ownership is checked here rather than only at the route: the route is a
    separate layer that could grow another caller, and a capability minted for
    someone else's recipe is a total compromise of that recipe.

    VIS-6: creating a share on a ``private`` recipe promotes it to ``unlisted``.
    It is never promoted to ``public`` -- that state is inert in this release
    (VIS-5) -- and an already-``unlisted`` recipe is left alone.
    """
    if getattr(owner, "id", None) is None or recipe.user_id != owner.id:
        # Deliberately says nothing about the recipe.
        raise PermissionError("Not the owner of this recipe")

    # UN-11, enforced here for the same reason ownership is: the route is a
    # separate layer that could grow another caller, and a share minted for an
    # account with an unconfirmed handle publishes something the account never
    # chose. An unconfirmed handle is derived from the email local part
    # (``anna.rossi@…`` becomes ``anna_rossi``), and the share page renders the
    # author's handle to anyone holding the link -- so minting the share is the
    # moment most of an email address becomes public. A second call site that
    # inherited the ownership check but not this one would leak silently.
    if not getattr(owner, "username_confirmed", False):
        raise HandleNotConfirmed(
            "Choose your username before sharing: a shared recipe shows the "
            "author's username publicly."
        )

    if mode not in models.SHARE_MODES:
        raise ValueError(f"Unsupported share mode: {mode!r}")

    email = models.normalize_email(recipient_email) if recipient_email else None
    if mode == "person" and recipient_user is None and not email:
        raise ValueError("A person share requires a recipient account or email")

    token = mint_token()
    share = RecipeShare(
        recipe_id=recipe.id,
        created_by_user_id=owner.id,
        token_hash=hash_token(token),
        mode=mode,
        recipient_user_id=recipient_user.id if recipient_user else None,
        recipient_email=email,
        expires_at=_as_naive_utc(expires_at),
    )
    session.add(share)

    if recipe.visibility == "private":
        recipe.visibility = "unlisted"

    session.flush()
    return share, token


# ---------------------------------------------------------------------------
# revocation and lazy demotion (VIS-7)
# ---------------------------------------------------------------------------
def revoke_share(
    session: Session, share: RecipeShare, *, at: datetime | None = None
) -> bool:
    """Revoke ``share``; return whether this call was the one that did it.

    An already-revoked share keeps its original timestamp: the stamp records
    when access was withdrawn and overwriting it would falsify that.
    """
    if share.revoked_at is not None:
        return False
    share.revoked_at = _as_naive_utc(at) or datetime.utcnow()
    session.flush()
    return True


def _has_active_share(
    session: Session, recipe_id: int, *, now: datetime | None = None
) -> bool:
    moment = _as_naive_utc(now) or datetime.utcnow()
    row = session.execute(
        select(RecipeShare.id)
        .where(
            RecipeShare.recipe_id == recipe_id,
            RecipeShare.revoked_at.is_(None),
            or_(
                RecipeShare.expires_at.is_(None),
                RecipeShare.expires_at > moment,
            ),
        )
        .limit(1)
    ).first()
    return row is not None


def demote_if_no_active_shares(
    session: Session, recipe: Recipe, *, now: datetime | None = None
) -> bool:
    """Demote an ``unlisted`` recipe back to ``private`` if nothing is live.

    Returns whether the visibility changed.

    VIS-7 covers *revocation or expiry*. Revocation has a call site; expiry does
    not, and this project has no scheduler -- adding one to flip a column would
    be disproportionate. So demotion on expiry is **lazy**: it is evaluated on
    the next read via :func:`effective_visibility`. The window in which the row
    still says ``unlisted`` grants nobody anything, because access always goes
    through :func:`resolve`, which rejects the expired share regardless.
    """
    if recipe.visibility != "unlisted":
        return False
    if _has_active_share(session, recipe.id, now=now):
        return False
    recipe.visibility = "private"
    session.flush()
    return True


def effective_visibility(
    session: Session, recipe: Recipe, *, now: datetime | None = None
) -> str:
    """The recipe's visibility, applying VIS-7's lazy demotion first."""
    demote_if_no_active_shares(session, recipe, now=now)
    return recipe.visibility


# ---------------------------------------------------------------------------
# Shared with me (SWM-1/3/4)
# ---------------------------------------------------------------------------
def active_shares_for_recipient(
    session: Session, user: User, *, now: datetime | None = None
) -> list[RecipeShare]:
    """Every live share addressed to ``user``, newest first.

    SWM-4: an account whose email is unverified gets an empty list. Matching on
    an unproven address would let anyone who can type someone else's email read
    what was sent to them, so verification gates *both* match arms -- including
    the account-id one, since an unverified account is not yet an account whose
    identity we will act on.

    SWM-3: entries the recipient dismissed are excluded. Dismissal is per
    recipient and leaves the share itself untouched, so the sharer's list and
    the token both keep working.
    """
    if not getattr(user, "email_verified", False):
        return []

    email = models.normalize_email(user.email) if user.email else None
    match_arms = [RecipeShare.recipient_user_id == user.id]
    if email:
        match_arms.append(RecipeShare.recipient_email == email)

    moment = _as_naive_utc(now) or datetime.utcnow()
    return list(
        session.execute(
            select(RecipeShare)
            .where(
                or_(*match_arms),
                RecipeShare.revoked_at.is_(None),
                RecipeShare.dismissed_by_recipient_at.is_(None),
                or_(
                    RecipeShare.expires_at.is_(None),
                    RecipeShare.expires_at > moment,
                ),
            )
            .order_by(RecipeShare.created_at.desc(), RecipeShare.id.desc())
        ).scalars().all()
    )


# ---------------------------------------------------------------------------
# URL construction (Q-1)
# ---------------------------------------------------------------------------
def _public_base_url() -> str:
    """Read ``PUBLIC_BASE_URL`` from the environment.

    Read here rather than imported from ``main``: ``main`` imports the routers,
    which import this module, so importing ``main`` would close a cycle. Read on
    each call rather than cached at import so tests (and a reconfigured process)
    see the current value.
    """
    return os.environ.get("PUBLIC_BASE_URL", "").rstrip("/")


def share_url(token: str, request=None) -> str:
    """Return the absolute URL a sharer forwards, ``{base}/s/{token}``.

    ``PUBLIC_BASE_URL`` wins when set. When it is unset the base is derived from
    the request -- which means the ``Host`` header, and **the ``Host`` header is
    attacker-controlled**. A forged ``Host`` on a share-creation request would
    return a link pointing at an attacker's origin; a sharer who then forwards
    it has handed the token to the attacker's server. Two mitigations here:

    1. The derived host is validated against a strict hostname pattern, so the
       obvious splices (``evil.example/@real``, embedded credentials, CR/LF)
       are refused rather than emitted.
    2. Falling back at all is logged as a warning, once per process.

    Neither makes a forged-but-well-formed ``Host`` safe. **Set
    ``PUBLIC_BASE_URL`` in any deployment** -- the fallback exists for dev,
    where the header is not attacker-controlled. A host allowlist belongs at the
    reverse proxy (or FastAPI's ``TrustedHostMiddleware``), which is outside
    this module's ownership; flagged for the supervisor.
    """
    base = _public_base_url()
    if not base:
        base = _base_url_from_request(request)
    return f"{base}{SHARE_PATH_PREFIX}{quote(token, safe='')}"


def _base_url_from_request(request) -> str:
    global _warned_about_host_fallback

    url = getattr(request, "url", None)
    host = getattr(url, "netloc", None) if url is not None else None
    scheme = getattr(url, "scheme", None) if url is not None else None
    if not host or not scheme:
        raise ValueError(
            "PUBLIC_BASE_URL is not set and no request is available to derive "
            "a share URL from"
        )
    if not _HOST_RE.match(host):
        raise ValueError("Refusing to build a share URL from a malformed Host header")

    if not _warned_about_host_fallback:
        _warned_about_host_fallback = True
        logger.warning(
            "PUBLIC_BASE_URL is unset; share URLs are being built from the "
            "request Host header (%s), which clients control. Set "
            "PUBLIC_BASE_URL in any non-development deployment.",
            host,
        )
    return f"{scheme}://{host}"
