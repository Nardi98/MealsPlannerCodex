"""The catalog service: publish/retire, listing, popularity and adoption (spec §6-§8, §13).

Every test builds on the ``system_account`` fixture, which empties the catalog
inside the test's transaction, so assertions are about rows the test created and
never about global counts (the bootstrap may have loaded the pack).
"""

from contextlib import contextmanager
from datetime import date

import pytest
from sqlalchemy import event, func, select
from sqlalchemy.orm import sessionmaker

import catalog
import crud
import models
import recipe_copy


@pytest.fixture
def db_session(engine):
    """``conftest.db_session``, but with every ``commit``/``rollback`` scoped to a SAVEPOINT.

    ``adopt`` commits once and rolls back on failure. Under the default join
    mode a session ``rollback()`` rolls back the test's *outer* transaction, so
    an all-or-nothing test would pass vacuously -- the fixtures would vanish
    along with the half-built batch. ``create_savepoint`` makes the service's
    commit and rollback behave as they do in production while the test's outer
    transaction still discards everything afterwards.
    """
    connection = engine.connect()
    trans = connection.begin()
    session = sessionmaker(
        bind=connection,
        autoflush=False,
        autocommit=False,
        future=True,
        join_transaction_mode="create_savepoint",
    )()
    try:
        yield session
    finally:
        session.close()
        trans.rollback()
        connection.close()


@contextmanager
def count_queries(engine):
    """Count the SQL statements the engine sends while the block runs."""
    statements = []

    def _record(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", _record)
    try:
        yield statements
    finally:
        event.remove(engine, "before_cursor_execute", _record)


@pytest.fixture
def make_system_recipe(db_session, system_account):
    """A system-owned recipe with **no** catalog entry, for publish tests."""

    def _make(title="Risotto", procedure="Stir.", ingredients=(("Rice", 80, "g"),)):
        recipe = models.Recipe(
            user_id=system_account.id, title=title, course="main", procedure=procedure
        )
        for name, quantity, unit in ingredients:
            ingredient = crud.get_or_create_ingredient(db_session, None, name, system_account.id)
            recipe.ingredients.append(
                models.RecipeIngredient(
                    ingredient=ingredient, quantity=quantity, unit=models.UnitEnum(unit)
                )
            )
        db_session.add(recipe)
        db_session.flush()
        return recipe

    return _make


# --- publish / retire (CAT-6..10, FC-2, FC-5, FC-8) -------------------------

def test_publish_creates_a_published_entry(db_session, make_system_recipe):
    recipe = make_system_recipe()

    catalog.publish(db_session, recipe)

    entry = db_session.get(models.CatalogEntry, recipe.id)
    assert entry is not None
    assert entry.status == "published"
    assert entry.published_at is not None
    assert entry.retired_at is None


def test_publish_and_retire_flush_but_never_commit(db_session, make_system_recipe, monkeypatch):
    """FC-5: the caller owns the transaction, so a future publish flow can reuse both."""
    recipe = make_system_recipe()
    commits = []
    monkeypatch.setattr(db_session, "commit", lambda: commits.append(1))

    catalog.publish(db_session, recipe)
    catalog.retire(db_session, recipe)

    assert commits == []
    status = db_session.execute(
        select(models.CatalogEntry.status).where(models.CatalogEntry.recipe_id == recipe.id)
    ).scalar_one()
    assert status == "retired"


def test_publishing_twice_keeps_published_at(db_session, make_system_recipe):
    recipe = make_system_recipe()
    catalog.publish(db_session, recipe)
    first = db_session.get(models.CatalogEntry, recipe.id).published_at

    catalog.publish(db_session, recipe)

    entry = db_session.get(models.CatalogEntry, recipe.id)
    assert entry.published_at == first
    assert entry.status == "published"


def test_retire_sets_status_and_retired_at_and_keeps_the_recipe(db_session, make_catalog_recipe):
    recipe = make_catalog_recipe("Lasagne")
    title_before = recipe.title

    catalog.retire(db_session, recipe)
    db_session.expire_all()

    entry = db_session.get(models.CatalogEntry, recipe.id)
    assert entry.status == "retired"
    assert entry.retired_at is not None
    kept = db_session.get(models.Recipe, recipe.id)
    assert kept is not None
    assert kept.title == title_before


def test_republishing_clears_retired_at_and_keeps_the_original_published_at(
    db_session, make_system_recipe
):
    recipe = make_system_recipe()
    catalog.publish(db_session, recipe)
    first = db_session.get(models.CatalogEntry, recipe.id).published_at
    catalog.retire(db_session, recipe)

    catalog.publish(db_session, recipe)

    entry = db_session.get(models.CatalogEntry, recipe.id)
    assert entry.status == "published"
    assert entry.retired_at is None
    assert entry.published_at == first


def test_retiring_an_uncatalogued_recipe_is_not_found(make_system_recipe, db_session):
    with pytest.raises(catalog.CatalogEntryNotFound):
        catalog.retire(db_session, make_system_recipe())


def test_retiring_a_retired_entry_is_a_no_op(db_session, make_catalog_recipe):
    recipe = make_catalog_recipe("Old", status="retired")
    retired_at = recipe.catalog_entry.retired_at

    catalog.retire(db_session, recipe)

    assert recipe.catalog_entry.status == "retired"
    assert recipe.catalog_entry.retired_at == retired_at


def test_publishing_a_user_owned_recipe_is_forbidden(db_session, system_account, make_recipe):
    recipe = make_recipe("Mine", procedure="Mix.")

    with pytest.raises(PermissionError):
        catalog.publish(db_session, recipe)

    assert db_session.get(models.CatalogEntry, recipe.id) is None


@pytest.mark.parametrize(
    "overrides, part",
    [
        ({"title": ""}, "title"),
        ({"title": "   "}, "title"),
        ({"ingredients": ()}, "ingredients"),
        ({"procedure": None}, "procedure"),
        ({"procedure": "  "}, "procedure"),
    ],
)
def test_publishing_an_incomplete_recipe_names_the_missing_part(
    db_session, make_system_recipe, overrides, part
):
    recipe = make_system_recipe(**overrides)

    with pytest.raises(catalog.IncompleteRecipe, match=part):
        catalog.publish(db_session, recipe)

    assert db_session.get(models.CatalogEntry, recipe.id) is None


# --- helpers ------------------------------------------------------------------

def _copy(db_session, source, person):
    """A copy made directly through ``recipe_copy``, so count tests do not rest on ``adopt``."""
    made = recipe_copy.duplicate(db_session, source, person)
    db_session.flush()
    return made


def _titles(rows):
    return [row.recipe.title for row in rows]


# --- list_published / get_published (CAT-4, CAT-5, RET-1, POP-7, ERR-11, API-20)

def test_listing_returns_published_entries_with_their_counts(
    db_session, make_catalog_recipe, user
):
    recipe = make_catalog_recipe("Pesto")
    _copy(db_session, recipe, user)

    rows = catalog.list_published(db_session)

    assert len(rows) == 1
    assert isinstance(rows[0], catalog.CatalogRow)
    assert rows[0].recipe.id == recipe.id
    assert rows[0].adoption_count == 1


def test_listing_hides_retired_and_uncatalogued_recipes(
    db_session, make_catalog_recipe, make_system_recipe
):
    make_catalog_recipe("Shown")
    make_catalog_recipe("Retired", status="retired")
    make_system_recipe(title="Never catalogued")

    assert _titles(catalog.list_published(db_session)) == ["Shown"]


def test_membership_is_the_entry_not_the_owner(db_session, system_account, make_recipe):
    """FC-1: a published entry on a user-owned recipe is listed like any other."""
    recipe = make_recipe("User published", procedure="Mix.")
    db_session.add(models.CatalogEntry(recipe_id=recipe.id, status="published"))
    db_session.flush()

    assert _titles(catalog.list_published(db_session)) == ["User published"]


def test_listing_without_a_system_account_raises_the_named_error(db_session, system_account):
    """ERR-5: a missing account is reported by name, not as an empty catalog."""
    db_session.delete(system_account)
    db_session.flush()

    with pytest.raises(catalog.SystemAccountMissing):
        catalog.list_published(db_session)


def test_course_filter_matches_any_of_the_given_courses(db_session, make_catalog_recipe):
    make_catalog_recipe("Roast", course="main")
    make_catalog_recipe("Salad", course="side")
    make_catalog_recipe("Soup", course="first-course")

    rows = catalog.list_published(db_session, course=["main", "side"], sort="title")

    assert _titles(rows) == ["Roast", "Salad"]


def test_a_single_course_string_is_one_course(db_session, make_catalog_recipe):
    make_catalog_recipe("Roast", course="main")
    make_catalog_recipe("Salad", course="side")

    assert _titles(catalog.list_published(db_session, course="side")) == ["Salad"]


def test_tag_filter_requires_every_given_tag(db_session, make_catalog_recipe):
    make_catalog_recipe("Both", tags=("vegan", "quick"))
    make_catalog_recipe("Vegan only", tags=("vegan",))
    make_catalog_recipe("Quick only", tags=("quick",))

    rows = catalog.list_published(db_session, tags=["vegan", "quick"])

    assert _titles(rows) == ["Both"]


def test_query_is_a_case_insensitive_title_substring(db_session, make_catalog_recipe):
    make_catalog_recipe("Spaghetti Carbonara")
    make_catalog_recipe("Risotto")

    assert _titles(catalog.list_published(db_session, query="CARBON")) == ["Spaghetti Carbonara"]


@pytest.mark.parametrize(
    "query, literal, pattern_only",
    [
        ("50%", "50% rye bread", "500 rye bread"),
        ("a_b", "a_b salad", "axb salad"),
        ("a\\b", "a\\b salad", "ab salad"),
    ],
)
def test_query_wildcards_match_literally(
    db_session, make_catalog_recipe, query, literal, pattern_only
):
    make_catalog_recipe(literal)
    make_catalog_recipe(pattern_only)

    assert _titles(catalog.list_published(db_session, query=query)) == [literal]


def test_popular_sorts_by_adopters_then_title(db_session, make_catalog_recipe, user, other_user):
    alpha = make_catalog_recipe("Alpha")
    beta = make_catalog_recipe("Beta")
    make_catalog_recipe("Delta")
    gamma = make_catalog_recipe("Gamma")
    for source, people in ((beta, (user, other_user)), (alpha, (user,)), (gamma, (other_user,))):
        for person in people:
            _copy(db_session, source, person)

    rows = catalog.list_published(db_session)

    assert [(r.recipe.title, r.adoption_count) for r in rows] == [
        ("Beta", 2), ("Alpha", 1), ("Gamma", 1), ("Delta", 0)
    ]
    assert _titles(catalog.list_published(db_session, sort="popular")) == _titles(rows)


def test_title_sort_ignores_popularity(db_session, make_catalog_recipe, user):
    make_catalog_recipe("Alpha")
    _copy(db_session, make_catalog_recipe("Beta"), user)

    assert _titles(catalog.list_published(db_session, sort="title")) == ["Alpha", "Beta"]


def test_an_unknown_sort_is_refused(db_session, system_account):
    with pytest.raises(ValueError, match="sort"):
        catalog.list_published(db_session, sort="newest")


def test_listing_is_capped(db_session, make_catalog_recipe, monkeypatch):
    for title in ("A", "B", "C"):
        make_catalog_recipe(title)
    monkeypatch.setattr(catalog, "LISTING_CAP", 2)

    assert _titles(catalog.list_published(db_session, sort="title")) == ["A", "B"]


def test_rendering_a_listing_issues_no_further_queries(db_session, engine, make_catalog_recipe):
    """CAT-5: ingredients (with each ingredient's row) and tags arrive with the listing."""
    for title in ("One", "Two", "Three"):
        make_catalog_recipe(
            title,
            ingredients=(("Pasta", 80, "g"), ("Olive oil", 10, "ml")),
            tags=("pasta", "quick"),
        )
    db_session.expunge_all()  # otherwise the identity map already holds the collections

    with count_queries(engine) as listing:
        rows = catalog.list_published(db_session)
    with count_queries(engine) as rendering:
        rendered = [
            (
                row.recipe.title, row.recipe.course, row.recipe.servings, row.recipe.bulk_prep,
                row.recipe.image_url, row.adoption_count,
                [t.name for t in row.recipe.tags],
                [(i.ingredient.name, i.quantity, i.unit) for i in row.recipe.ingredients],
            )
            for row in rows
        ]

    assert len(rendered) == 3
    assert all(len(r[7]) == 2 and len(r[6]) == 2 for r in rendered)
    assert rendering == []
    # A constant number of statements, whatever the size of the listing.
    assert len(listing) <= 5, listing


def test_get_published_returns_the_row(db_session, make_catalog_recipe, user):
    recipe = make_catalog_recipe("Pesto")
    _copy(db_session, recipe, user)

    row = catalog.get_published(db_session, recipe.id)

    assert row.recipe.id == recipe.id
    assert row.adoption_count == 1


def test_get_published_refuses_anything_not_published(
    db_session, make_catalog_recipe, make_system_recipe, make_recipe, user
):
    retired = make_catalog_recipe("Old", status="retired")
    uncatalogued = make_system_recipe()
    users_own = make_recipe("Mine")
    copy_of_entry = _copy(db_session, make_catalog_recipe("Pesto"), user)

    for recipe_id in (retired.id, uncatalogued.id, users_own.id, copy_of_entry.id, 10**9):
        with pytest.raises(catalog.CatalogEntryNotFound):
            catalog.get_published(db_session, recipe_id)


# --- adoption_counts (POP-1..4, ERR-10, RET-4, FC-3) -------------------------

def test_adoption_counts_is_one_query(db_session, engine, make_catalog_recipe, user, other_user):
    first = make_catalog_recipe("First")
    second = make_catalog_recipe("Second")
    _copy(db_session, first, user)
    _copy(db_session, second, other_user)

    with count_queries(engine) as statements:
        counts = catalog.adoption_counts(db_session, [first.id, second.id])

    assert counts == {first.id: 1, second.id: 1}
    assert len(statements) == 1


def test_adoption_counts_report_zero_for_unadopted_ids(db_session, make_catalog_recipe):
    recipe = make_catalog_recipe("Lonely")
    assert catalog.adoption_counts(db_session, [recipe.id]) == {recipe.id: 0}


def test_adoption_counts_count_people_not_copies(db_session, make_catalog_recipe, user):
    recipe = make_catalog_recipe("Pesto")
    _copy(db_session, recipe, user)
    _copy(db_session, recipe, user)

    assert catalog.adoption_counts(db_session, [recipe.id]) == {recipe.id: 1}


def test_adoption_counts_exclude_the_system_account(
    db_session, make_catalog_recipe, system_account, user
):
    recipe = make_catalog_recipe("Pesto")
    _copy(db_session, recipe, system_account)
    _copy(db_session, recipe, user)

    assert catalog.adoption_counts(db_session, [recipe.id]) == {recipe.id: 1}


def test_deleting_a_copy_drops_the_count(db_session, make_catalog_recipe, user, other_user):
    recipe = make_catalog_recipe("Pesto")
    _copy(db_session, recipe, other_user)
    mine = _copy(db_session, recipe, user)

    db_session.delete(mine)
    db_session.flush()

    assert catalog.adoption_counts(db_session, [recipe.id]) == {recipe.id: 1}


def test_a_retired_entry_keeps_its_count(db_session, make_catalog_recipe, user):
    recipe = make_catalog_recipe("Pesto")
    _copy(db_session, recipe, user)

    catalog.retire(db_session, recipe)

    assert catalog.adoption_counts(db_session, [recipe.id]) == {recipe.id: 1}


def test_adoption_counts_work_for_a_user_owned_source(db_session, system_account, make_recipe, other_user):
    """FC-3: nothing in the count assumes the source belongs to the system account."""
    recipe = make_recipe("Ragu")
    _copy(db_session, recipe, other_user)

    assert catalog.adoption_counts(db_session, [recipe.id]) == {recipe.id: 1}


# --- held_by (API-3) ----------------------------------------------------------

def test_held_by_reports_each_users_own_copies(
    db_session, engine, make_catalog_recipe, user, other_user
):
    pesto = make_catalog_recipe("Pesto")
    ragu = make_catalog_recipe("Ragu")
    soup = make_catalog_recipe("Soup")
    _copy(db_session, pesto, user)
    _copy(db_session, ragu, user)
    _copy(db_session, ragu, other_user)
    ids = [pesto.id, ragu.id, soup.id]

    with count_queries(engine) as statements:
        mine = catalog.held_by(db_session, user, ids)

    assert mine == {pesto.id, ragu.id}
    assert len(statements) == 1
    assert catalog.held_by(db_session, other_user, ids) == {ragu.id}
