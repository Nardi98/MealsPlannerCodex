"""The system recipe catalog ("Discover") -- all of its domain logic (CAT-1).

Routers translate HTTP to calls on this module and back; they hold no catalog
logic of their own. In the other direction this module **must not** import
``main``, any router module (``*_routes``, ``public_pages``) or anything from
``frontend-v2`` (CAT-11), so the service stays callable from startup, the seed
scripts and a future self-service publish flow alike (FC-5).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

import models
from mealplanner.seed import seed_system_ingredients, seed_system_tags

__all__ = [
    "SYSTEM_ACCOUNT_USERNAME",
    "SYSTEM_ACCOUNT_EMAIL",
    "LISTING_CAP",
    "ADOPT_BATCH_MAX",
    "SystemAccountMissing",
    "CatalogEntryNotFound",
    "IncompleteRecipe",
    "system_user",
    "ensure_system_account",
]

#: SYS-3. Used **only** when the account is created (SYS-6): everything else
#: finds it by ``User.is_system``, so renaming it is a one-row UPDATE.
SYSTEM_ACCOUNT_USERNAME = "mealplanner"
SYSTEM_ACCOUNT_EMAIL = "mealplanner@localhost"

#: API-20: the hard cap on one catalog listing. The catalog ships with 60
#: entries; past this cap, pagination is the intended next step.
LISTING_CAP = 500

#: ADO-15: the most recipe ids one adopt call accepts -- comfortably above the
#: shipped 60, so "select all and add" keeps working as the catalog grows.
ADOPT_BATCH_MAX = 100


class SystemAccountMissing(RuntimeError):
    """No ``is_system`` account exists (CAT-3, ERR-5)."""


class CatalogEntryNotFound(LookupError):
    """The recipe is not a catalog entry in the state the caller needs."""


class IncompleteRecipe(ValueError):
    """The recipe cannot be published; ``str(e)`` names the missing part (CAT-10)."""


def system_user(session: Session) -> models.User:
    """The account that owns the catalog, resolved by its flag (SYS-6).

    Raises :class:`SystemAccountMissing` rather than returning ``None``, so a
    missing account fails here with its name on it instead of later as an
    ``AttributeError`` somewhere else (CAT-3).
    """
    account = session.execute(
        select(models.User).where(models.User.is_system.is_(True))
    ).scalar_one_or_none()
    if account is None:
        raise SystemAccountMissing("catalog: no is_system account exists")
    return account


def ensure_system_account(session: Session) -> models.User:
    """Get or create the system account, with its own tags and ingredients.

    Idempotent, so it is safe on every start. No password, no Google identity
    and an unverified address leave no login path (SYS-5). The handle is
    recorded as chosen (SYS-12), and nothing consults the reserved list, which
    is enforced only at the route layer (SYS-10). The tags and ingredients are
    re-seeded on every call; both seeders skip what already exists (SYS-8).

    The row is built here rather than through ``crud.create_user``, because
    that function commits before ``is_system`` could be set. A crash, or a
    second instance starting at the same moment, would then leave a committed
    ``mealplanner`` user *without* the flag. SYS-6 forbids finding the account
    by its handle, so nothing could recognise that row, and every later start
    would fail trying to create the handle again. Here the row is only ever
    flushed carrying the flag, and the seeders' commit lands it all together.
    """
    try:
        account = system_user(session)
    except SystemAccountMissing:
        account = models.User(
            email=SYSTEM_ACCOUNT_EMAIL,
            username=SYSTEM_ACCOUNT_USERNAME,
            hashed_password=None,
            google_sub=None,
            auth_provider="local",
            email_verified=False,
            is_system=True,
            username_changed_at=datetime.utcnow(),
        )
        session.add(account)
        session.flush()
    seed_system_tags(session, account.id)
    seed_system_ingredients(session, account.id)
    return account
