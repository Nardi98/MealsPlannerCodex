"""The system recipe catalog ("Discover") -- all of its domain logic (CAT-1).

Routers translate HTTP to calls on this module and back; they hold no catalog
logic of their own. In the other direction this module **must not** import
``main``, any router module (``*_routes``, ``public_pages``) or anything from
``frontend-v2`` (CAT-11), so the service stays callable from startup, the seed
scripts and a future self-service publish flow alike (FC-5).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import Select, distinct, func, select
from sqlalchemy.orm import Session, aliased, contains_eager, selectinload

import models
import recipe_copy
from mealplanner.seed import seed_system_ingredients, seed_system_tags

__all__ = [
    "SYSTEM_ACCOUNT_USERNAME",
    "SYSTEM_ACCOUNT_EMAIL",
    "LISTING_CAP",
    "ADOPT_BATCH_MAX",
    "SystemAccountMissing",
    "CatalogEntryNotFound",
    "IncompleteRecipe",
    "CatalogRow",
    "AdoptResult",
    "system_user",
    "ensure_system_account",
    "list_published",
    "get_published",
    "adoption_counts",
    "held_by",
    "adopt",
    "publish",
    "retire",
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


@dataclass(frozen=True)
class CatalogRow:
    """One published entry as a listing sees it: the recipe and its adopter count."""

    recipe: models.Recipe
    adoption_count: int


@dataclass(frozen=True)
class AdoptResult:
    """What one adopt call did: the new recipes' ids and the source ids already held."""

    created_ids: list[int]
    skipped_ids: list[int]


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


# --- Popularity (POP-1..4, FC-3) ---------------------------------------------


def _adopter_counts(source_ids) -> Select:
    """``COUNT(DISTINCT owner)`` of the copies of each of ``source_ids``.

    Derived from ``source_recipe_id`` (POP-1), so deleting a copy lowers the
    count with no bookkeeping (ERR-10) and a retired entry keeps its history
    (RET-4). Copies the system account holds are not adoptions (POP-3); it is
    excluded by its flag, and nothing here assumes the *source* is system-owned
    (FC-3). ``source_ids`` is anything ``in_`` accepts, a subquery included.
    """
    copy = aliased(models.Recipe)
    return (
        select(
            copy.source_recipe_id.label("recipe_id"),
            func.count(distinct(copy.user_id)).label("adoption_count"),
        )
        .join(models.User, models.User.id == copy.user_id)
        .where(copy.source_recipe_id.in_(source_ids), models.User.is_system.is_(False))
        .group_by(copy.source_recipe_id)
    )


def adoption_counts(session: Session, recipe_ids: Iterable[int]) -> dict[int, int]:
    """How many distinct users hold a copy of each recipe, in one query (POP-4).

    Every requested id is in the result; one nobody adopted maps to ``0``.
    """
    counts = dict.fromkeys(recipe_ids, 0)
    counts.update(session.execute(_adopter_counts(list(counts))).tuples().all())
    return counts


def held_by(session: Session, user: models.User, recipe_ids: Iterable[int]) -> set[int]:
    """Which of ``recipe_ids`` ``user`` already holds a copy of, in one query (API-3)."""
    return set(
        session.execute(
            select(models.Recipe.source_recipe_id)
            .where(
                models.Recipe.user_id == user.id,
                models.Recipe.source_recipe_id.in_(list(recipe_ids)),
            )
            .distinct()
        ).scalars()
    )


# --- Browsing (CAT-4, CAT-5, API-1, API-5, API-20) ---------------------------


def _escape_like(text: str) -> str:
    """``text`` with LIKE's metacharacters made literal, for ``escape="\\\\"`` (ERR-11)."""
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _published_rows(session: Session, criteria: list, sort: str) -> list[CatalogRow]:
    """Published entries matching ``criteria``, with counts and eager relations.

    Membership is a ``published`` entry and nothing else -- there is no
    ownership filter, so a user-published recipe would join by its entry alone
    (P2-1, FC-1). The count is an outer join on one grouped subquery, and the
    ingredients (with each ingredient row, whose name callers render) and tags
    are loaded by ``selectinload``, so the statement count is the same for one
    row or five hundred (CAT-5).
    """
    # ERR-5: with no system account the catalog is broken, not empty. Say so by
    # name instead of returning a quiet ``[]``.
    system_user(session)

    published = models.CatalogEntry.status == "published"
    counts = _adopter_counts(
        select(models.CatalogEntry.recipe_id).where(published)
    ).subquery()
    adoption_count = func.coalesce(counts.c.adoption_count, 0)
    ordering = {"popular": [adoption_count.desc()], "title": []}[sort]

    stmt = (
        select(models.Recipe, adoption_count)
        .join(models.Recipe.catalog_entry)
        .outerjoin(counts, counts.c.recipe_id == models.Recipe.id)
        .where(published, *criteria)
        .options(
            contains_eager(models.Recipe.catalog_entry),
            selectinload(models.Recipe.ingredients).joinedload(models.RecipeIngredient.ingredient),
            selectinload(models.Recipe.tags),
        )
        # POP-7; the id makes equal titles deterministic too.
        .order_by(*ordering, models.Recipe.title.asc(), models.Recipe.id.asc())
        .limit(LISTING_CAP)
    )
    return [CatalogRow(recipe, count) for recipe, count in session.execute(stmt).tuples()]


def list_published(
    session: Session,
    *,
    course: str | Iterable[str] | None = None,
    tags: Iterable[str] | None = None,
    query: str | None = None,
    sort: str = "popular",
) -> list[CatalogRow]:
    """The catalog listing: published entries, filtered, sorted and capped.

    ``course`` matches any of the given courses; ``tags`` must all be present;
    ``query`` is a case-insensitive literal substring of the title. ``sort`` is
    ``"popular"`` (adopters descending, then title) or ``"title"``. At most
    :data:`LISTING_CAP` rows are returned.
    """
    if sort not in ("popular", "title"):
        raise ValueError(f"catalog: unknown sort {sort!r}; expected 'popular' or 'title'")

    criteria = []
    if course:
        courses = [course] if isinstance(course, str) else list(course)
        criteria.append(models.Recipe.course.in_(courses))
    for name in tags or ():
        criteria.append(models.Recipe.tags.any(models.Tag.name == name))
    if query:
        criteria.append(models.Recipe.title.ilike(f"%{_escape_like(query)}%", escape="\\"))
    return _published_rows(session, criteria, sort)


def get_published(session: Session, recipe_id: int) -> CatalogRow:
    """One published entry, or :class:`CatalogEntryNotFound` (API-5).

    Retired, never-catalogued and other users' recipes are all simply not found:
    the caller cannot tell them apart.
    """
    rows = _published_rows(session, [models.Recipe.id == recipe_id], "title")
    if not rows:
        raise CatalogEntryNotFound(f"catalog: recipe {recipe_id} is not published")
    return rows[0]


# --- Adoption (ADO-1..16, ERR-1..4, ERR-12, PRV-6) ---------------------------


def adopt(session: Session, user: models.User, recipe_ids: Iterable[int]) -> AdoptResult:
    """Copy published catalog recipes into ``user``'s book, all or nothing.

    Only published entries can be adopted: any other id -- retired, never
    catalogued, someone's private recipe, a user's copy of an entry -- raises
    :class:`CatalogEntryNotFound` before anything is written, so this is never a
    general-purpose recipe copier (ADO-14, PRV-6). A recipe the user already
    holds a copy of is skipped (ADO-7). Each copy is made by
    :func:`recipe_copy.duplicate`, never ``copy_recipe``, so favourite sides stay
    behind (ADO-2). The batch lands in exactly one commit and any failure rolls
    all of it back (ADO-5, ADO-6).

    ``created_ids`` and ``skipped_ids`` follow the source ids in ascending order.
    """
    requested = list(recipe_ids)
    if not requested:
        raise ValueError("catalog: choose at least one recipe to adopt")
    if len(requested) > ADOPT_BATCH_MAX:
        raise ValueError(f"catalog: at most {ADOPT_BATCH_MAX} recipes can be adopted at once")
    ids = set(requested)

    # ERR-5, as for the listing: a missing account is named, not a 404.
    system_user(session)

    sources = session.execute(
        select(models.Recipe)
        .join(models.Recipe.catalog_entry)
        .where(models.Recipe.id.in_(ids), models.CatalogEntry.status == "published")
        .order_by(models.Recipe.id)
    ).scalars().all()
    missing = ids - {source.id for source in sources}
    if missing:
        raise CatalogEntryNotFound(f"catalog: not published: {sorted(missing)}")

    try:
        # ERR-12 under concurrency. ``existing_copy`` then insert is a race on
        # its own: two simultaneous submits could both find nothing held. Locking
        # the adopter's row makes a second adopt by the same user wait for this
        # one to commit, after which its ``existing_copy`` sees these copies.
        # ``NO KEY UPDATE`` still conflicts with itself but not with the key-share
        # locks that inserting any row referencing this user takes.
        session.execute(
            select(models.User.id).where(models.User.id == user.id).with_for_update(key_share=True)
        )
        made, skipped_ids = [], []
        # Ascending source ids, so concurrent batches from different users take
        # the source rows' copy_count locks in the same order.
        for source in sources:
            if recipe_copy.existing_copy(session, source, user) is not None:
                skipped_ids.append(source.id)
                continue
            made.append(recipe_copy.duplicate(session, source, user))
            # ADO-16. Incremented in SQL so concurrent adopters do not lose counts.
            source.copy_count = models.Recipe.copy_count + 1
        session.flush()
        result = AdoptResult(created_ids=[recipe.id for recipe in made], skipped_ids=skipped_ids)
        session.commit()
    except Exception:
        session.rollback()
        raise
    return result


# --- Curation (CAT-6..10) ----------------------------------------------------
#
# Both functions flush and never commit: the caller owns the transaction, so the
# admin routes today and a self-service publish flow later call them unchanged
# (FC-5).


def _missing_part(recipe: models.Recipe) -> str | None:
    """The first thing CAT-10 requires that ``recipe`` lacks, or ``None``."""
    if not (recipe.title or "").strip():
        return "title"
    if not recipe.ingredients:
        return "ingredients"
    if not (recipe.procedure or "").strip():
        return "procedure"
    return None


def publish(session: Session, recipe: models.Recipe) -> models.CatalogEntry:
    """Put ``recipe`` in the catalog, or bring a retired entry back (CAT-6, CAT-7).

    Idempotent. ``published_at`` is written once, when the entry is created, and
    survives every later retire and re-publish (FC-8).
    """
    # --- CAT-9 / FC-2: only the system account's recipes may be published. ---
    # This is the single place that restriction lives. Membership itself does
    # not depend on ownership (FC-1), so letting users publish their own
    # recipes later means deleting this block and nothing else.
    if recipe.user_id != system_user(session).id:
        raise PermissionError("catalog: only system-owned recipes can be published")

    missing = _missing_part(recipe)
    if missing is not None:
        raise IncompleteRecipe(f"catalog: the recipe has no {missing}")

    entry = recipe.catalog_entry
    if entry is None:
        entry = models.CatalogEntry(status="published", published_at=datetime.utcnow())
        recipe.catalog_entry = entry
    elif entry.status == "retired":
        entry.status = "published"
        entry.retired_at = None
    session.flush()
    return entry


def retire(session: Session, recipe: models.Recipe) -> models.CatalogEntry:
    """Hide ``recipe`` from the catalog without deleting anything (CAT-8, RET-1..4).

    The entry row stays, so the adoption count and ``published_at`` are there
    when it is re-published. Retiring a retired entry changes nothing.
    """
    entry = recipe.catalog_entry
    if entry is None:
        raise CatalogEntryNotFound(f"catalog: recipe {recipe.id} is not catalogued")
    if entry.status != "retired":
        entry.status = "retired"
        entry.retired_at = datetime.utcnow()
        session.flush()
    return entry
