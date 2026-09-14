"""The system recipe catalog ("Discover") -- all of its domain logic (CAT-1).

Routers translate HTTP to calls on this module and back; they hold no catalog
logic of their own. In the other direction this module **must not** import
``main``, any router module (``*_routes``, ``public_pages``) or anything from
``frontend-v2`` (CAT-11), so the service stays callable from startup, the seed
scripts and a future self-service publish flow alike (FC-5).
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from sqlalchemy import Select, distinct, func, select
from sqlalchemy.orm import Session, aliased, contains_eager, selectinload

import crud
import models
import recipe_copy
from mealplanner.seed import seed_system_ingredients, seed_system_tags

__all__ = [
    "SYSTEM_ACCOUNT_USERNAME",
    "SYSTEM_ACCOUNT_EMAIL",
    "LISTING_CAP",
    "ADOPT_BATCH_MAX",
    "PACK_PATH",
    "POPULATE_LOCK_KEY",
    "SystemAccountMissing",
    "CatalogEntryNotFound",
    "IncompleteRecipe",
    "CatalogRow",
    "AdoptResult",
    "system_user",
    "ensure_system_account",
    "populate_from_pack",
    "list_published",
    "get_published",
    "adoption_counts",
    "held_by",
    "adopt",
    "publish",
    "retire",
    "list_all",
    "create_catalog_recipe",
    "update_catalog_recipe",
    "export_catalog",
    "ingredient_lines",
    "system_ingredients",
    "system_tags",
]

#: SYS-3. Used **only** when the account is created (SYS-6): everything else
#: finds it by ``User.is_system``, so renaming it is a one-row UPDATE.
SYSTEM_ACCOUNT_USERNAME = "mealplanner"
SYSTEM_ACCOUNT_EMAIL = "mealplanner@localhost"

#: INIT-1: the recipes the catalog ships with. Resolved from this file rather
#: than the working directory, so startup finds it wherever it is launched.
PACK_PATH = Path(__file__).resolve().parent / "data" / "catalog_pack.json"

#: The ``pg_advisory_xact_lock`` key serialising :func:`populate_from_pack`
#: across instances. Any fixed bigint works; it only has to be unique among the
#: app's advisory locks, and this is the only one. (ASCII "catpack".)
POPULATE_LOCK_KEY = 0x6361747061636B

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
    # The bare column, not ``.is_(True)``, so Postgres can use the partial index
    # ``uq_user_single_system``; ``is_system`` is NOT NULL, so the rows are the same.
    account = session.execute(select(models.User).where(models.User.is_system)).scalar_one_or_none()
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


def populate_from_pack(session: Session, path: Path = PACK_PATH) -> int:
    """Load the pack into an empty catalog; return how many entries were created.

    Runs on every start (INIT-8, INIT-13), so it does nothing once the system
    account holds *any* catalog entry, retired ones included (INIT-10): it never
    updates or reconciles an existing catalog recipe, and an admin's edit
    survives every restart (INIT-11). Ingredient and tag names resolve in the
    system account's own namespace, onto the rows its seeders created, so the
    recipes carry real seasonality and conversions (INIT-9, SYS-8).

    Each entry is created ``published`` whatever the file says: an export file
    carries ``status``, ``published_at`` and ``retired_at``, which are ignored
    (EXP-5). The recipes stay ``private`` (P2-2). The whole pack lands in one
    commit and any failure rolls it all back, so a start never leaves half a
    catalog that INIT-10 would then refuse to complete.
    """
    system = ensure_system_account(session)
    # INIT-13 across instances: two starting together would both find the
    # catalog empty and load it twice. The second now waits here until the
    # first commits, then finds it full. Taken only now, because
    # ``ensure_system_account`` commits and a transaction-scoped lock taken
    # before it would already have been released.
    session.execute(select(func.pg_advisory_xact_lock(POPULATE_LOCK_KEY)))
    populated = session.execute(
        select(models.CatalogEntry.recipe_id)
        .join(models.Recipe, models.Recipe.id == models.CatalogEntry.recipe_id)
        .where(models.Recipe.user_id == system.id)
        .limit(1)
    ).first()
    if populated is not None:
        # Release the lock by ending its transaction. Commit, not rollback:
        # ``ensure_system_account`` has just committed, so the transaction holds
        # nothing but the lock and this read, and a commit cannot discard work
        # a caller left pending, which a rollback would if that ever changed.
        session.commit()
        return 0

    items = json.loads(path.read_text(encoding="utf-8"))
    try:
        # The system vocabulary, read once. A name the seeders did not create
        # falls back to ``get_or_create_*`` in the same namespace, as before.
        ingredients = {row.name: row for row in _owned_by(session, models.Ingredient, system)}
        tags = {row.name: row for row in _owned_by(session, models.Tag, system)}

        def ingredient(name: str) -> models.Ingredient:
            if name not in ingredients:
                ingredients[name] = crud.get_or_create_ingredient(session, None, name, system.id)
            return ingredients[name]

        def tag(name: str) -> models.Tag:
            if name not in tags:
                tags[name] = crud.get_or_create_tag(session, name, system.id)
            return tags[name]

        for item in items:
            # Resolved before the recipe joins the session: a fallback flushes,
            # and must not flush a recipe whose fields are not written yet.
            lines = [(ingredient(line["name"]), line["quantity"], line["unit"]) for line in item["ingredients"]]
            item_tags = [tag(name) for name in item["tags"]]
            recipe = models.Recipe(
                user_id=system.id,
                visibility="private",
                catalog_entry=models.CatalogEntry(
                    status="published", published_at=datetime.utcnow(), retired_at=None
                ),
            )
            session.add(recipe)
            # ``_write`` reads only the pack's fields, so an export's extra keys are ignored (EXP-5).
            _write(session, recipe, item, lines, item_tags)
        session.commit()
    except Exception:
        session.rollback()
        raise
    return len(items)


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
        .where(copy.source_recipe_id.in_(source_ids), ~models.User.is_system)
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


#: Every line with its ingredient row (whose name callers render), and the tags,
#: each in one statement whatever the number of recipes (CAT-5).
_LINES_AND_TAGS = (
    selectinload(models.Recipe.ingredients).joinedload(models.RecipeIngredient.ingredient),
    selectinload(models.Recipe.tags),
)
#: For a query already joined to the entry: the entry from that join, plus the above.
_ENTRY_LINES_AND_TAGS = (contains_eager(models.Recipe.catalog_entry), *_LINES_AND_TAGS)


def _escape_like(text: str) -> str:
    """``text`` with LIKE's metacharacters made literal, for ``escape="\\\\"`` (ERR-11)."""
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _catalog_rows(
    session: Session, criteria: list, sort: str, *, published_only: bool = True
) -> list[CatalogRow]:
    """Entries matching ``criteria``, with counts and eager relations.

    Membership is an entry and nothing else -- ``published`` unless
    ``published_only`` is false, which the admin listing uses to see retired
    entries too (API-9). There is no ownership filter, so a user-published
    recipe would join by its entry alone (P2-1, FC-1). The count is an outer
    join on one grouped subquery, and the ingredients (with each ingredient row,
    whose name callers render) and tags are loaded by ``selectinload``, so the
    statement count is the same for one row or five hundred (CAT-5).
    """
    # ERR-5: with no system account the catalog is broken, not empty. Say so by
    # name instead of returning a quiet ``[]``.
    system_user(session)

    membership = [models.CatalogEntry.status == "published"] if published_only else []
    counts = _adopter_counts(
        select(models.CatalogEntry.recipe_id).where(*membership)
    ).subquery()
    adoption_count = func.coalesce(counts.c.adoption_count, 0)
    ordering = {"popular": [adoption_count.desc()], "title": []}[sort]

    stmt = (
        select(models.Recipe, adoption_count)
        .join(models.Recipe.catalog_entry)
        .outerjoin(counts, counts.c.recipe_id == models.Recipe.id)
        .where(*membership, *criteria)
        .options(*_ENTRY_LINES_AND_TAGS)
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
    return _catalog_rows(session, criteria, sort)


def get_published(session: Session, recipe_id: int) -> CatalogRow:
    """One published entry, or :class:`CatalogEntryNotFound` (API-5).

    Retired, never-catalogued and other users' recipes are all simply not found:
    the caller cannot tell them apart.
    """
    rows = _catalog_rows(session, [models.Recipe.id == recipe_id], "title")
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

    # ERR-5, as for the listing: a missing account is named, not a 404. Held in
    # a local for the whole call, so ``duplicate``'s lookup of each source's
    # author finds it in the identity map instead of selecting it again.
    system = system_user(session)  # noqa: F841

    # Each source's ingredients and tags arrive with it, not lazily per copy.
    sources = session.execute(
        select(models.Recipe)
        .join(models.Recipe.catalog_entry)
        .where(models.Recipe.id.in_(ids), models.CatalogEntry.status == "published")
        .options(*_LINES_AND_TAGS)
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


# --- Administration (§9, §9.1, API-9..13, D3) ---------------------------------
#
# ``data`` is a plain mapping: ``title``, ``course``, ``servings``, ``bulk_prep``,
# ``procedure``, ``image_url``, ``tags`` (names) and ``ingredients`` (``name``,
# ``quantity``, ``unit``). Validating its shape is the router's job; this module
# resolves the names and owns the rules. Like publish/retire, these functions
# flush and never commit.

#: ``create_catalog_recipe``'s ``publish`` flag shadows the function inside it.
_publish = publish


def list_all(session: Session) -> list[CatalogRow]:
    """Every entry, published and retired, by title, with adoption counts (API-9, RET-4).

    A draft -- a system recipe with no entry yet -- is not an entry and is not
    listed. Capped at :data:`LISTING_CAP`, like the user-facing listing.
    """
    return _catalog_rows(session, [], "title", published_only=False)


def _resolve_names(session: Session, system: models.User, data) -> tuple[list, list[models.Tag]]:
    """``data``'s ingredient lines and tags, bound to the system account's rows.

    Names resolve **only** onto rows the system account already owns: nothing
    is created, and the admin's own pantry and tags are never consulted, so
    authoring can neither grow the shared vocabulary by a typo nor touch the
    admin's data (D3, ADM-12). Matching is exact, as it is in
    ``crud.get_or_create_ingredient`` and ``crud.get_or_create_tag``. Callers
    resolve before writing anything, so an unknown name leaves no partial rows.

    Returns ``([(ingredient, quantity, unit), ...], [tag, ...])``; repeated tag
    names collapse to one.
    """
    names = [line["name"] for line in data["ingredients"]]
    ingredients = {
        row.name: row
        for row in session.scalars(
            select(models.Ingredient).where(
                models.Ingredient.user_id == system.id, models.Ingredient.name.in_(names)
            )
        )
    }
    seen = set()
    for name in names:
        if name not in ingredients:
            raise ValueError(f"Unknown ingredient: {name}")
        if name in seen:
            # One line per ingredient per recipe: the association's primary key.
            raise ValueError(f"Duplicate ingredient: {name}")
        seen.add(name)

    tag_names = list(dict.fromkeys(data["tags"]))
    tags = {
        row.name: row
        for row in session.scalars(
            select(models.Tag).where(models.Tag.user_id == system.id, models.Tag.name.in_(tag_names))
        )
    }
    for name in tag_names:
        if name not in tags:
            raise ValueError(f"Unknown tag: {name}")

    lines = [(ingredients[line["name"]], line["quantity"], line["unit"]) for line in data["ingredients"]]
    return lines, [tags[name] for name in tag_names]


def _write(session: Session, recipe: models.Recipe, data, lines: list, tags: list[models.Tag]) -> None:
    """Write every field of ``recipe`` from ``data`` and its resolved names.

    Ingredients and tags are replaced wholesale; a line whose ingredient the
    recipe already had becomes an UPDATE of that row at flush.
    """
    for field in ("title", "course", "servings", "bulk_prep", "procedure"):
        setattr(recipe, field, data[field])
    recipe.image_url = data.get("image_url")
    recipe.ingredients.clear()
    recipe.ingredients.extend(
        models.RecipeIngredient(ingredient=ingredient, quantity=quantity, unit=models.UnitEnum(unit))
        for ingredient, quantity, unit in lines
    )
    recipe.tags = tags
    session.flush()


def create_catalog_recipe(session: Session, data, *, publish: bool = True) -> models.Recipe:
    """Create a system-owned recipe and, by default, its published entry (API-10, ADM-7).

    Owned by the account found by its flag (SYS-6) and ``private`` (P2-2).
    With ``publish`` the entry goes through :func:`publish`, so CAT-10 rejects
    an incomplete recipe with :class:`IncompleteRecipe`; its rows are flushed
    by then, so the caller must roll back rather than commit. With
    ``publish=False`` the recipe is a draft with no entry until it is published.
    """
    system = system_user(session)
    lines, tags = _resolve_names(session, system, data)
    recipe = models.Recipe(user_id=system.id, visibility="private")
    session.add(recipe)
    _write(session, recipe, data, lines, tags)
    if publish:
        _publish(session, recipe)
    return recipe


def update_catalog_recipe(session: Session, recipe_id: int, data) -> models.Recipe:
    """Rewrite a catalog recipe from ``data`` (API-11).

    A catalog recipe is one the system account owns, catalogued or still a
    draft; anything else -- another account's recipe, or no recipe -- raises
    :class:`CatalogEntryNotFound`. This is not CAT-9's publish rule (FC-2): an
    admin may never edit someone else's recipe, whoever may publish later
    (ADM-9). Adopters' copies are their own rows and are not re-synced.

    A **published** entry must stay complete (CAT-10), so the result is checked
    by :func:`publish`, which changes nothing else for it; on
    :class:`IncompleteRecipe` the caller must roll back. A retired entry or a
    draft may be left incomplete, and publishing it checks again.
    """
    system = system_user(session)
    recipe = session.get(models.Recipe, recipe_id)
    if recipe is None or recipe.user_id != system.id:
        raise CatalogEntryNotFound(f"catalog: recipe {recipe_id} is not a catalog recipe")
    lines, tags = _resolve_names(session, system, data)
    _write(session, recipe, data, lines, tags)
    if recipe.catalog_entry is not None and recipe.catalog_entry.status == "published":
        _publish(session, recipe)
    return recipe


def ingredient_lines(recipe: models.Recipe) -> list[dict]:
    """``recipe``'s ingredient lines as ``{"name", "quantity", "unit"}`` dicts.

    ``unit`` is the plain string value, or ``None``. The one extraction the export
    and both routers' bodies share; each router still picks its own fields.
    """
    return [
        {
            "name": line.ingredient.name,
            "quantity": line.quantity,
            "unit": line.unit.value if line.unit is not None else None,
        }
        for line in recipe.ingredients
    ]


def _iso(moment: datetime | None) -> str | None:
    return moment.isoformat() if moment is not None else None


def export_catalog(session: Session) -> list[dict]:
    """The whole catalog, published and retired, as pack-shaped dicts by title (§9.1).

    A superset of the pack format (EXP-4): the pack's fields plus ``status``,
    ``published_at`` and ``retired_at`` as ISO strings, which the loader ignores
    (EXP-5). Nothing about people is included: no ids, counts, emails or
    handles (EXP-3). Uncapped, because a backup that silently dropped entries
    would be worse than none.
    """
    system_user(session)
    recipes = session.scalars(
        select(models.Recipe)
        .join(models.Recipe.catalog_entry)
        .options(*_ENTRY_LINES_AND_TAGS)
        .order_by(models.Recipe.title.asc(), models.Recipe.id.asc())
    ).all()
    return [
        {
            "title": recipe.title,
            "course": recipe.course,
            "servings": recipe.servings,
            "bulk_prep": bool(recipe.bulk_prep),
            "tags": [tag.name for tag in recipe.tags],
            "procedure": recipe.procedure,
            "ingredients": ingredient_lines(recipe),
            "status": recipe.catalog_entry.status,
            "published_at": _iso(recipe.catalog_entry.published_at),
            "retired_at": _iso(recipe.catalog_entry.retired_at),
        }
        for recipe in recipes
    ]


def _owned_by(session: Session, model, owner: models.User) -> list:
    """Every ``model`` row (an ingredient or a tag) ``owner`` owns, by name."""
    return list(session.scalars(select(model).where(model.user_id == owner.id).order_by(model.name)))


def system_ingredients(session: Session) -> list[models.Ingredient]:
    """The system account's ingredients by name: the names catalog recipes may use (D3)."""
    system = system_user(session)
    return list(
        session.scalars(
            select(models.Ingredient)
            .where(models.Ingredient.user_id == system.id)
            .order_by(models.Ingredient.name)
        )
    )


def system_tags(session: Session) -> list[models.Tag]:
    """The system account's tags by name (D3)."""
    system = system_user(session)
    return list(
        session.scalars(select(models.Tag).where(models.Tag.user_id == system.id).order_by(models.Tag.name))
    )
