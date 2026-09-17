"""T8: the catalog is populated from the pack at startup (INIT-8..13, EXP-5, TST-4).

``main`` imports run :func:`main._bootstrap`, and conftest removes what that
loaded once per run, so these tests call the loader explicitly. Each still
starts from a known empty catalog -- the ``system_account`` fixture clears the
entries, or the system account is removed outright -- inside a transaction that
is rolled back afterwards.
"""

import json
from contextlib import contextmanager

import pytest
from sqlalchemy import event, func, select

import catalog
import main
import models
from mealplanner.seed import SYSTEM_INGREDIENTS, SYSTEM_TAGS

PACK = json.loads(catalog.PACK_PATH.read_text(encoding="utf-8"))


def _entries(session, status=None):
    stmt = (
        select(func.count())
        .select_from(models.CatalogEntry)
        .join(models.Recipe, models.Recipe.id == models.CatalogEntry.recipe_id)
        .join(models.User, models.User.id == models.Recipe.user_id)
        .where(models.User.is_system.is_(True))
    )
    if status is not None:
        stmt = stmt.where(models.CatalogEntry.status == status)
    return session.scalar(stmt)


def _catalog_recipes(session):
    return session.execute(
        select(models.Recipe).join(models.Recipe.catalog_entry)
    ).scalars().all()


def _write_pack(tmp_path, items):
    path = tmp_path / "pack.json"
    path.write_text(json.dumps(items), encoding="utf-8")
    return path


def test_populate_creates_the_system_account_and_sixty_published_entries(db_session):
    """INIT-9, starting from a database with no system account at all."""
    from conftest import remove_system_catalog

    remove_system_catalog(db_session)
    assert db_session.scalar(select(models.User.id).where(models.User.is_system.is_(True))) is None

    created = catalog.populate_from_pack(db_session)

    assert created == len(PACK) == 60
    system = catalog.system_user(db_session)
    assert system.username == catalog.SYSTEM_ACCOUNT_USERNAME
    assert _entries(db_session) == 60
    assert _entries(db_session, "published") == 60


def test_loaded_recipes_bind_to_the_system_accounts_seeded_rows(db_session, system_account):
    """INIT-9 / SYS-8: real seasonality, not all-year defaults invented on the fly."""
    catalog.populate_from_pack(db_session)

    recipes = _catalog_recipes(db_session)
    assert recipes
    for recipe in recipes:
        assert all(ri.ingredient.user_id == system_account.id for ri in recipe.ingredients)
        assert all(tag.user_id == system_account.id for tag in recipe.tags)

    # Nothing outside the seeded vocabulary was created for the account.
    owned_ingredients = db_session.scalar(
        select(func.count()).select_from(models.Ingredient)
        .where(models.Ingredient.user_id == system_account.id)
    )
    owned_tags = db_session.scalar(
        select(func.count()).select_from(models.Tag).where(models.Tag.user_id == system_account.id)
    )
    assert owned_ingredients == len(SYSTEM_INGREDIENTS)
    assert owned_tags == len(SYSTEM_TAGS)

    seasons = {entry["name"]: entry["season_months"] for entry in SYSTEM_INGREDIENTS}
    used = {ri.ingredient for recipe in recipes for ri in recipe.ingredients}
    by_name = {ingredient.name: ingredient for ingredient in used}
    for name in ("Tomato", "Basil"):
        assert by_name[name].season_months == seasons[name]


def test_loaded_recipes_are_private_and_match_the_pack(db_session, system_account):
    """P2-2, INIT-7: fields and quantities as authored."""
    catalog.populate_from_pack(db_session)

    by_title = {recipe.title: recipe for recipe in _catalog_recipes(db_session)}
    assert set(by_title) == {item["title"] for item in PACK}
    for item in PACK:
        recipe = by_title[item["title"]]
        assert recipe.visibility == "private"
        assert recipe.user_id == system_account.id
        assert recipe.course == item["course"]
        assert recipe.servings == item["servings"]
        assert recipe.bulk_prep == item["bulk_prep"]
        assert recipe.procedure == item["procedure"]
        assert sorted(tag.name for tag in recipe.tags) == sorted(item["tags"])
        assert sorted(
            (ri.ingredient.name, ri.quantity, ri.unit.value) for ri in recipe.ingredients
        ) == sorted((i["name"], i["quantity"], i["unit"]) for i in item["ingredients"])
        assert recipe.catalog_entry.status == "published"
        assert recipe.catalog_entry.published_at is not None
        assert recipe.catalog_entry.retired_at is None


def test_bootstrap_twice_leaves_sixty_entries(db_session, system_account):
    """INIT-8, INIT-10, INIT-13, TST-4."""
    main._bootstrap(db_session)
    main._bootstrap(db_session)

    assert _entries(db_session) == 60


def test_an_edited_catalog_recipe_survives_a_second_bootstrap(db_session, system_account):
    """INIT-11, TST-4."""
    main._bootstrap(db_session)
    recipe = _catalog_recipes(db_session)[0]
    original = recipe.title
    recipe.title = "Edited by an admin"
    db_session.commit()

    main._bootstrap(db_session)

    db_session.expire_all()
    assert db_session.get(models.Recipe, recipe.id).title == "Edited by an admin"
    assert original not in {r.title for r in _catalog_recipes(db_session)}
    assert _entries(db_session) == 60


def test_a_retired_entry_alone_stops_the_pack_being_reapplied(db_session, make_catalog_recipe):
    """INIT-10: retired entries count."""
    make_catalog_recipe("Retired one", status="retired")

    assert catalog.populate_from_pack(db_session) == 0

    assert _entries(db_session) == 1
    assert _entries(db_session, "published") == 0


def test_an_export_file_loads_with_every_entry_published(db_session, system_account, tmp_path):
    """EXP-5: the export's extra fields are accepted and ignored."""
    exported = [
        {
            **item,
            "status": "retired",
            "published_at": "2026-01-01T00:00:00",
            "retired_at": "2026-02-01T00:00:00",
        }
        for item in PACK
    ]

    created = catalog.populate_from_pack(db_session, path=_write_pack(tmp_path, exported))

    assert created == 60
    assert _entries(db_session, "published") == 60
    assert all(r.catalog_entry.retired_at is None for r in _catalog_recipes(db_session))


def _count(session, stmt):
    return session.scalar(select(func.count()).select_from(stmt.subquery()))


def test_the_test_run_cleanup_removes_the_import_time_catalog(db_session, user):
    """conftest's one-time cleanup: back to the pre-catalog state, reservations kept."""
    import usernames
    from conftest import remove_system_catalog

    usernames.seed_reserved(db_session)
    main._bootstrap(db_session)
    system = catalog.system_user(db_session)
    system_id = system.id
    source = _catalog_recipes(db_session)[0]
    copy = models.Recipe(user_id=user.id, title="My copy", source_recipe_id=source.id)
    db_session.add(copy)
    db_session.flush()

    remove_system_catalog(db_session)
    db_session.expire_all()

    assert db_session.scalar(select(models.User.id).where(models.User.is_system.is_(True))) is None
    assert db_session.get(models.User, system_id) is None
    for model in (models.Recipe, models.Ingredient, models.Tag):
        assert _count(db_session, select(model.id).where(model.user_id == system_id)) == 0
    assert _count(db_session, select(models.CatalogEntry.recipe_id)) == 0
    # Copies survive, unlinked by ``ON DELETE SET NULL``.
    assert db_session.get(models.Recipe, copy.id).source_recipe_id is None
    assert db_session.get(models.ReservedUsername, catalog.SYSTEM_ACCOUNT_USERNAME) is not None


def test_the_test_run_cleanup_is_a_no_op_without_a_system_account(db_session, user):
    from conftest import remove_system_catalog

    remove_system_catalog(db_session)  # whatever the DB held, there is no account now
    reserved = _count(db_session, select(models.ReservedUsername.username))

    remove_system_catalog(db_session)
    db_session.expire_all()

    assert db_session.get(models.User, user.id) is not None
    assert _count(db_session, select(models.ReservedUsername.username)) == reserved
    assert db_session.scalar(select(models.User.id).where(models.User.is_system.is_(True))) is None


@contextmanager
def _statements(engine):
    seen = []

    def _record(conn, cursor, statement, parameters, context, executemany):
        seen.append(statement)

    event.listen(engine, "before_cursor_execute", _record)
    try:
        yield seen
    finally:
        event.remove(engine, "before_cursor_execute", _record)


def _lock_then_emptiness_check(statements):
    locks = [i for i, s in enumerate(statements) if "pg_advisory_xact_lock" in s]
    checks = [i for i, s in enumerate(statements) if "FROM catalog_entries JOIN recipes" in s]
    return locks, checks


@pytest.mark.parametrize("already_populated", [False, True])
def test_populate_takes_the_advisory_lock_before_checking_emptiness(
    db_session, engine, make_catalog_recipe, already_populated
):
    """Two instances starting together: the second waits, then finds the catalog full."""
    if already_populated:
        make_catalog_recipe("Existing")

    with _statements(engine) as statements:
        catalog.populate_from_pack(db_session)

    locks, checks = _lock_then_emptiness_check(statements)
    assert len(locks) == 1
    assert len(checks) == 1
    assert locks[0] < checks[0]


def test_the_early_return_commits_to_release_the_lock(
    db_session, engine, make_catalog_recipe, monkeypatch
):
    """``return 0`` ends the lock's transaction with a commit, never a rollback."""
    make_catalog_recipe("Existing")
    real_commit, real_rollback = db_session.commit, db_session.rollback

    with _statements(engine) as timeline:
        monkeypatch.setattr(db_session, "commit", lambda: (timeline.append("COMMIT()"), real_commit())[1])
        monkeypatch.setattr(db_session, "rollback", lambda: (timeline.append("ROLLBACK()"), real_rollback())[1])
        assert catalog.populate_from_pack(db_session) == 0

    _, checks = _lock_then_emptiness_check(timeline)
    assert "COMMIT()" in timeline[checks[0]:]
    assert "ROLLBACK()" not in timeline


def test_loading_the_pack_resolves_names_without_a_query_per_line(db_session, engine, system_account):
    """The system vocabulary is read once, not looked up per ingredient line and tag."""
    with _statements(engine) as statements:
        assert catalog.populate_from_pack(db_session) == 60

    lookups = [s for s in statements if "ingredients.name = %(" in s or "tags.name = %(" in s]
    assert lookups == []
    # Each recipe is flushed on its own: one INSERT each into recipes,
    # catalog_entries, recipe_ingredients and recipe_tag. Everything else is a
    # small constant; per-line lookups used to cost over a thousand statements.
    assert len(statements) <= 4 * len(PACK) + 25, len(statements)


def test_a_bad_item_writes_nothing(db_session, system_account, tmp_path):
    """One commit for the whole pack: a failure part-way leaves no half catalog."""
    broken = [PACK[0], {**PACK[1], "ingredients": [{"name": "Salt", "quantity": 1, "unit": "cup"}]}]

    with pytest.raises(ValueError):
        catalog.populate_from_pack(db_session, path=_write_pack(tmp_path, broken))

    assert _entries(db_session) == 0
