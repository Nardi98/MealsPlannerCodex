"""Reviewed batch import into the catalog, and the system vocabulary writes.

A bulk import cannot be a silent bulk insert. ``catalog._resolve_names``
resolves strictly on purpose -- an unknown name is refused and nothing is
auto-created, so a typo can never grow the shared vocabulary -- and a system
ingredient is not just a name: it carries the seasonality and the conversions
the planner's scoring and the shopping list read. Any realistic file therefore
arrives naming things the system account does not own, and someone has to say
what each of them is.

So an upload is *staged*, not applied: every entry becomes a
:class:`models.CatalogImportItem` the admin walks through, resolving names,
fixing what the file got wrong and committing each recipe as a draft as they
go. Publishing stays the separate action it already was.

Like ``catalog``, this module is pure domain logic: routers translate HTTP to
calls on it and back, and it **must not** import ``main``, any router module or
anything from ``frontend-v2``, so it stays callable from a script as well as a
request.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

import catalog
import crud
import models
from scoping import scope

__all__ = [
    "COURSES",
    "UNITS",
    "ITEM_FIELDS",
    "OPEN_STATES",
    "ImportBatchNotFound",
    "ImportItemNotFound",
    "VocabularyNotFound",
    "VocabularyInUse",
    "open_batch",
    "get_batch",
    "get_item",
    "stage_upload",
    "update_item",
    "skip_item",
    "commit_item",
    "prune_if_finished",
    "item_problems",
    "duplicate_of",
    "create_system_ingredient",
    "update_system_ingredient",
    "delete_system_ingredient",
    "ingredient_usage",
    "create_system_tag",
    "update_system_tag",
    "delete_system_tag",
    "tag_usage",
]

#: The courses the app authors recipes in -- the planner's main-slot courses and
#: sides. The same tuple the admin recipe form validates against.
COURSES = (*models.MAIN_COURSES, models.SIDE_COURSE)

#: The units a stored quantity may carry: one per dimension. Derived from the
#: storage enum so the validator and the column can never disagree.
UNITS = tuple(unit.value for unit in models.UnitEnum)

#: The fields a draft keeps. An export file is a superset of the pack format --
#: it carries ``status``, ``published_at`` and ``retired_at`` -- and those are
#: curation state, not recipe fields, so normalising drops them. The untouched
#: ``source`` still has them if anyone asks what the file said.
ITEM_FIELDS = (
    "title",
    "course",
    "servings",
    "bulk_prep",
    "procedure",
    "image_url",
    "tags",
    "ingredients",
)

#: The item states that still need a human. A batch lives exactly as long as one
#: of them remains; a batch's state is never stored, only derived. ``models``
#: owns the vocabulary (it is also the column's CHECK).
OPEN_STATES = models.IMPORT_ITEM_OPEN_STATES


class ImportBatchNotFound(LookupError):
    """No staged batch with that id."""


class ImportItemNotFound(LookupError):
    """No staged item with that id."""


class VocabularyNotFound(LookupError):
    """No system-owned ingredient or tag with that id.

    A row another account owns raises this too: the admin console curates the
    system namespace and nobody else's (ADM-12).
    """


class VocabularyInUse(ValueError):
    """Refused: recipes still reference the row. ``count`` says how many."""

    def __init__(self, message: str, count: int) -> None:
        super().__init__(message)
        self.count = count


# --- staging -----------------------------------------------------------------


def _line_problem(line: Any) -> str | None:
    """Why ``line`` is not a usable ingredient line, or ``None``."""
    if not isinstance(line, dict):
        return "each ingredient must be an object"
    name = line.get("name")
    if not isinstance(name, str) or not name.strip():
        return "each ingredient needs a name"
    quantity = line.get("quantity")
    if isinstance(quantity, bool) or not isinstance(quantity, (int, float)):
        return f"{name}: quantity must be a number"
    if quantity <= 0:
        return f"{name}: quantity must be greater than 0"
    if line.get("unit") not in UNITS:
        return f"{name}: unit must be one of {', '.join(UNITS)}"
    return None


def _entry_problem(entry: Any) -> str | None:
    """Why ``entry`` cannot become a recipe, or ``None``.

    The same field rules the admin recipe form enforces, applied here so one bad
    entry is staged ``invalid`` with its reason instead of rejecting the file.
    """
    if not isinstance(entry, dict):
        return "each entry must be an object"
    title = entry.get("title")
    if not isinstance(title, str) or not title.strip():
        return "title is required"
    if entry.get("course") not in COURSES:
        return f"course must be one of {', '.join(COURSES)}"
    servings = entry.get("servings")
    if isinstance(servings, bool) or not isinstance(servings, int):
        return "servings must be a whole number"
    if servings < 1:
        return "servings must be greater than or equal to 1"
    if not isinstance(entry.get("bulk_prep"), bool):
        return "bulk_prep must be true or false"
    for field in ("procedure", "image_url"):
        value = entry.get(field)
        if value is not None and not isinstance(value, str):
            return f"{field} must be text"
    tags = entry.get("tags")
    if not isinstance(tags, list) or not all(isinstance(t, str) for t in tags):
        return "tags must be a list of names"
    lines = entry.get("ingredients")
    if not isinstance(lines, list) or not lines:
        return "at least one ingredient is required"
    for line in lines:
        problem = _line_problem(line)
        if problem is not None:
            return problem
    names = [line["name"] for line in lines]
    if len(set(names)) != len(names):
        # One line per ingredient per recipe: the association's primary key.
        return "the same ingredient is listed twice"
    return None


def _normalise(session: Session, system: models.User, entry: Any) -> dict:
    """``entry`` reduced to the draft's shape, with what already resolves marked.

    Resolution state lives inside the draft: each line keeps its name plus a
    nullable ``ingredient_id`` pointing at the system row it resolved onto.
    ``None`` is the case the review page exists for.
    """
    draft = {field: entry.get(field) for field in ITEM_FIELDS} if isinstance(entry, dict) else {}
    lines = draft.get("ingredients")
    if not isinstance(lines, list):
        return draft
    known = _ingredients_by_name(
        session, system, [ln.get("name") for ln in lines if isinstance(ln, dict)]
    )
    draft["ingredients"] = [
        {
            **line,
            "ingredient_id": _line_ingredient_id(line, known),
        }
        if isinstance(line, dict)
        else line
        for line in lines
    ]
    return draft


def _line_ingredient_id(line: dict, known: dict[str, models.Ingredient]) -> int | None:
    """The system ingredient ``line`` resolves onto, preferring an explicit pick.

    An ``ingredient_id`` the admin chose on the review page wins over the name,
    so resolving a misspelt line onto an existing row does not force a rename.
    """
    chosen = line.get("ingredient_id")
    if isinstance(chosen, int):
        return chosen
    row = known.get(line.get("name"))
    return row.id if row is not None else None


def _ingredients_by_name(
    session: Session, system: models.User, names: Iterable[Any]
) -> dict[str, models.Ingredient]:
    wanted = [name for name in names if isinstance(name, str)]
    if not wanted:
        return {}
    stmt = select(models.Ingredient).where(models.Ingredient.name.in_(wanted))
    rows = session.scalars(scope(stmt, models.Ingredient.user_id, system.id))
    return {row.name: row for row in rows}


def duplicate_of(
    session: Session, title: Any, system: models.User | None = None
) -> int | None:
    """The catalogued recipe already carrying ``title``, if there is one.

    Computed once at upload and stored, because it drives the side-by-side view
    and a duplicate is flagged rather than skipped: deciding what to do with it
    is the admin's, not the importer's. ``system`` is the account the caller has
    already resolved, if it has one -- staging asks this per entry, and looking
    the account up once per file rather than once per recipe is the difference.
    """
    if not isinstance(title, str):
        return None
    system = system or catalog.system_user(session)
    return session.scalars(
        select(models.Recipe.id)
        .join(models.Recipe.catalog_entry)
        .where(models.Recipe.user_id == system.id, models.Recipe.title == title)
        .order_by(models.Recipe.id)
        .limit(1)
    ).first()


def stage_upload(
    session: Session,
    admin: models.User,
    filename: str,
    entries: Sequence[Any],
) -> models.CatalogImportBatch:
    """Stage ``entries`` as one batch for ``admin`` to review.

    Every entry lands, whatever shape it is in: a malformed one is staged
    ``invalid`` carrying the reason, so a single bad entry costs one recipe
    rather than the file. Nothing is written to the catalog here -- the batch is
    a to-do list, and each recipe is created only when its item is committed.

    Flushes so the rows have ids; the caller owns the commit.
    """
    system = catalog.system_user(session)
    batch = models.CatalogImportBatch(created_by_user_id=admin.id, filename=filename)
    session.add(batch)
    for position, entry in enumerate(entries):
        problem = _entry_problem(entry)
        batch.items.append(
            models.CatalogImportItem(
                position=position,
                source=entry,
                draft=_normalise(session, system, entry),
                state="invalid" if problem else "pending",
                error=problem,
                duplicate_recipe_id=(
                    None if problem else duplicate_of(session, entry.get("title"), system)
                ),
            )
        )
    session.flush()
    return batch


# --- review ------------------------------------------------------------------


def open_batch(session: Session) -> models.CatalogImportBatch | None:
    """The batch still under review, if any.

    One at a time by construction: a finished batch is pruned, so at most one
    normally exists. The newest wins if a previous one was somehow abandoned.
    """
    return session.scalars(
        select(models.CatalogImportBatch)
        .order_by(models.CatalogImportBatch.created_at.desc(), models.CatalogImportBatch.id.desc())
        .limit(1)
    ).first()


def get_batch(session: Session, batch_id: int) -> models.CatalogImportBatch:
    batch = session.get(models.CatalogImportBatch, batch_id)
    if batch is None:
        raise ImportBatchNotFound(f"catalog import: no batch {batch_id}")
    return batch


def get_item(session: Session, item_id: int) -> models.CatalogImportItem:
    item = session.get(models.CatalogImportItem, item_id)
    if item is None:
        raise ImportItemNotFound(f"catalog import: no item {item_id}")
    return item


def update_item(session: Session, item_id: int, draft: Any) -> models.CatalogImportItem:
    """Replace the item's working copy and re-derive its state.

    ``source`` is never touched: an edit answers "what should this recipe be",
    never "what did the file say". An entry edited back into shape stops being
    ``invalid``, and one edited out of shape becomes ``invalid`` again -- the
    state is a fact about the draft, not a verdict recorded at upload.
    """
    item = get_item(session, item_id)
    system = catalog.system_user(session)
    problem = _entry_problem(draft)
    item.draft = _normalise(session, system, draft)
    item.state = "invalid" if problem else "pending"
    item.error = problem
    session.flush()
    return item


def item_problems(
    session: Session, item: models.CatalogImportItem, system: models.User | None = None
) -> list[str]:
    """Everything standing between ``item`` and a committable recipe.

    An item is committable only when it parses, every ingredient line resolves
    onto a system ingredient and every tag already exists -- the strictness
    ``catalog._resolve_names`` will apply anyway, reported here in full rather
    than one exception at a time, so the review page can list the work left.

    ``system`` is the account the caller has already resolved, if it has one: a
    whole batch is asked this at once, and that is one lookup instead of one per
    item.
    """
    problem = _entry_problem(item.draft)
    if problem is not None:
        return [problem]

    system = system or catalog.system_user(session)
    problems = []
    lines = item.draft["ingredients"]
    known = _ingredients_by_name(session, system, [line["name"] for line in lines])
    for line in lines:
        if _line_ingredient_id(line, known) is None:
            problems.append(f"Unknown ingredient: {line['name']}")

    names = list(dict.fromkeys(item.draft["tags"]))
    if names:
        stmt = select(models.Tag.name).where(models.Tag.name.in_(names))
        found = set(session.scalars(scope(stmt, models.Tag.user_id, system.id)))
        problems.extend(f"Unknown tag: {name}" for name in names if name not in found)
    return problems


def skip_item(session: Session, item_id: int) -> models.CatalogImportItem:
    """Leave this entry out of the catalog. Reversible only by re-uploading."""
    item = get_item(session, item_id)
    item.state = "skipped"
    item.error = None
    session.flush()
    return item


def commit_item(session: Session, item_id: int) -> models.Recipe:
    """Turn the item's draft into a system-owned **draft** recipe.

    The write itself is ``catalog.create_catalog_recipe``, so an imported recipe
    is built by exactly the code that builds a hand-authored one; there is no
    second writer to keep in step. ``publish=False``: committing lands a draft,
    and publishing stays the existing separate action.

    Raises ``ValueError`` if the item is already finished or anything is still
    unresolved -- committing half a recipe is what the review exists to prevent.
    """
    item = get_item(session, item_id)
    if item.state not in OPEN_STATES:
        raise ValueError(f"catalog import: item {item_id} is already {item.state}")
    problems = item_problems(session, item)
    if problems:
        raise ValueError("; ".join(problems))

    recipe = catalog.create_catalog_recipe(session, _for_write(session, item), publish=False)
    item.state = "committed"
    item.error = None
    item.committed_recipe_id = recipe.id
    session.flush()
    return recipe


def _for_write(session: Session, item: models.CatalogImportItem) -> dict:
    """The draft in the shape ``catalog.create_catalog_recipe`` reads.

    A line resolved by id is written under **that row's** name, so picking an
    existing ingredient for a misspelt line imports it correctly without the
    admin having to retype the name.
    """
    system = catalog.system_user(session)
    data = {field: item.draft.get(field) for field in ITEM_FIELDS}
    data["ingredients"] = [
        {
            "name": _resolved_name(session, system, line),
            "quantity": line["quantity"],
            "unit": line["unit"],
        }
        for line in item.draft["ingredients"]
    ]
    return data


def _resolved_name(session: Session, system: models.User, line: dict) -> str:
    chosen = line.get("ingredient_id")
    if isinstance(chosen, int):
        ingredient = crud.get_ingredient(session, chosen, system.id)
        if ingredient is not None:
            return ingredient.name
    return line["name"]


def prune_if_finished(session: Session, batch: models.CatalogImportBatch) -> bool:
    """Delete ``batch`` when nothing is left to review; return whether it went.

    A batch is scaffolding, so it is cleaned up the moment it has no work in it
    rather than kept as history nobody asked for. Called after every commit and
    every skip, which is when the last open item can disappear.
    """
    if any(item.state in OPEN_STATES for item in batch.items):
        return False
    session.delete(batch)
    session.flush()
    return True


# --- system vocabulary -------------------------------------------------------
#
# Growing the shared vocabulary is exactly what ``catalog._resolve_names``
# refuses to do implicitly, so it is done here explicitly, by an admin, in the
# system namespace alone.


def _system_row(session: Session, model, row_id: int):
    """``row_id`` of ``model``, only if the system account owns it."""
    system = catalog.system_user(session)
    row = session.get(model, row_id)
    if row is None or row.user_id != system.id:
        raise VocabularyNotFound(f"catalog: {model.__tablename__} {row_id} is not system-owned")
    return row


def _refuse_duplicate(session: Session, model, name: str, exclude_id: int | None = None) -> None:
    """The (user_id, name) unique constraint, enforced as a message not a 500."""
    system = catalog.system_user(session)
    stmt = select(model.id).where(model.name == name)
    if exclude_id is not None:
        stmt = stmt.where(model.id != exclude_id)
    if session.scalars(scope(stmt, model.user_id, system.id)).first() is not None:
        raise ValueError(f"{name} already exists")


def create_system_ingredient(
    session: Session,
    *,
    name: str,
    season_months: list[int] | None = None,
    categories: list[str] | None = None,
    grams_per_ml: float | None = None,
    grams_per_piece: float | None = None,
    preferred_dimension: models.DimensionEnum | None = None,
) -> models.Ingredient:
    """Add a name to the system vocabulary, with the physics that go with it.

    The row is built here rather than through ``crud.create_ingredient``, which
    commits: the router owns the transaction, so a failure later in the request
    must still take this with it.
    """
    system = catalog.system_user(session)
    name = _required_name(name)
    _refuse_duplicate(session, models.Ingredient, name)
    ingredient = models.Ingredient(
        user_id=system.id,
        name=name,
        season_months=season_months or [],
        categories=categories or [],
        grams_per_ml=grams_per_ml,
        grams_per_piece=grams_per_piece,
        preferred_dimension=preferred_dimension,
    )
    session.add(ingredient)
    session.flush()
    return ingredient


_UNSET = object()


def update_system_ingredient(
    session: Session,
    ingredient_id: int,
    *,
    name: str | None = None,
    season_months: list[int] | None = _UNSET,
    categories: list[str] | None = _UNSET,
    grams_per_ml: float | None = _UNSET,
    grams_per_piece: float | None = _UNSET,
    preferred_dimension: models.DimensionEnum | None = _UNSET,
) -> models.Ingredient:
    """Correct a system ingredient in place.

    Every field given is written, ``None`` included: this is the page that
    exists so a wrong ``grams_per_piece`` can be *cleared* without psql, which a
    backfill-only update could never do. A field left out is left alone.
    """
    ingredient = _system_row(session, models.Ingredient, ingredient_id)
    if name is not None:
        name = _required_name(name)
        _refuse_duplicate(session, models.Ingredient, name, exclude_id=ingredient_id)
        ingredient.name = name
    for field, value in (
        ("season_months", season_months),
        ("categories", categories),
        ("grams_per_ml", grams_per_ml),
        ("grams_per_piece", grams_per_piece),
        ("preferred_dimension", preferred_dimension),
    ):
        if value is not _UNSET:
            setattr(ingredient, field, value)
    session.flush()
    return ingredient


def ingredient_usage(session: Session, ingredient_id: int) -> int:
    """How many recipes carry this ingredient, whoever owns them.

    Unscoped on purpose: the question is whether deleting the row would break a
    recipe, and a recipe in another account's book breaks just as badly as a
    system one. Counted in the database, like :func:`tag_usage`: the link table
    has one row per (recipe, ingredient) pair, so counting it is the number of
    recipes without hydrating any of them.

    Raises :class:`VocabularyNotFound` for a row the system account does not
    own, so asking about someone else's pantry is never answered.
    """
    _system_row(session, models.Ingredient, ingredient_id)
    return session.scalar(
        select(func.count())
        .select_from(models.RecipeIngredient)
        .where(models.RecipeIngredient.ingredient_id == ingredient_id)
    )


def delete_system_ingredient(session: Session, ingredient_id: int) -> None:
    """Remove an unused name from the vocabulary.

    Refused with :class:`VocabularyInUse` while any recipe references it -- the
    association cascades, so forcing it would silently delete ingredient *lines*
    from finished recipes. Merging two ingredients is a different operation and
    deliberately not this one.
    """
    ingredient = _system_row(session, models.Ingredient, ingredient_id)
    used = ingredient_usage(session, ingredient_id)
    if used:
        raise VocabularyInUse(f"{ingredient.name} is used by {used} recipe(s)", used)
    session.delete(ingredient)
    session.flush()


def create_system_tag(
    session: Session, *, name: str, penalize_repetition: bool = False
) -> models.Tag:
    """Add a tag to the system vocabulary.

    ``is_system`` is set: these are the labels catalog recipes carry, and the
    flag is what tells them apart from a name a user happened to choose.
    """
    system = catalog.system_user(session)
    name = _required_name(name)
    _refuse_duplicate(session, models.Tag, name)
    tag = models.Tag(
        user_id=system.id,
        name=name,
        penalize_repetition=penalize_repetition,
        is_system=True,
    )
    session.add(tag)
    session.flush()
    return tag


def update_system_tag(
    session: Session,
    tag_id: int,
    *,
    name: str | None = None,
    penalize_repetition: bool | None = None,
) -> models.Tag:
    """Rename a system tag, and set whether repeating it is penalised.

    Renaming rather than delete-and-recreate keeps the tag's recipes attached:
    the link table holds ids, so every recipe carrying it follows the new name.
    """
    tag = _system_row(session, models.Tag, tag_id)
    if name is not None:
        name = _required_name(name)
        _refuse_duplicate(session, models.Tag, name, exclude_id=tag_id)
        tag.name = name
    if penalize_repetition is not None:
        tag.penalize_repetition = penalize_repetition
    session.flush()
    return tag


def tag_usage(session: Session, tag_id: int) -> int:
    """How many recipes carry this tag -- the count the confirm dialog shows.

    Scoped like :func:`ingredient_usage`: a tag the system account does not own
    raises :class:`VocabularyNotFound`.
    """
    _system_row(session, models.Tag, tag_id)
    link = models.recipe_tag_table.c
    return session.scalar(
        select(func.count()).select_from(models.recipe_tag_table).where(link.tag_id == tag_id)
    )


def delete_system_tag(session: Session, tag_id: int) -> None:
    """Remove a tag, detaching it from every recipe that carried it.

    Unlike an ingredient this is allowed while in use: a tag carries no physics
    and no quantity, so losing one costs a label and nothing else. The caller
    shows :func:`tag_usage` first so the cost is stated before it is paid.
    """
    tag = _system_row(session, models.Tag, tag_id)
    # Detached through the relationship rather than by a DELETE on the link
    # table: ``recipe_tag`` does not cascade, and a core delete would leave any
    # already-loaded ``recipe.tags`` still holding the tag it no longer has.
    tag.recipes.clear()
    session.delete(tag)
    session.flush()


def _required_name(name: Any) -> str:
    if not isinstance(name, str) or not name.strip():
        raise ValueError("name is required")
    return name.strip()
