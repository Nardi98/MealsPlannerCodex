"""T8: the catalog is populated from the pack at startup (INIT-8..13, EXP-5, TST-4).

``main`` imports run :func:`main._bootstrap`, so the test database already holds
a populated catalog by the time these tests run. Every test here therefore
starts from a known empty catalog -- the ``system_account`` fixture clears the
entries, or the system account is removed outright -- inside a transaction that
is rolled back afterwards.
"""

import json

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.orm import sessionmaker

import catalog
import main
import models
from mealplanner.seed import SYSTEM_INGREDIENTS, SYSTEM_TAGS

PACK = json.loads(catalog.PACK_PATH.read_text(encoding="utf-8"))


@pytest.fixture
def db_session(engine):
    """``conftest.db_session``, but with every ``commit``/``rollback`` scoped to a SAVEPOINT.

    ``populate_from_pack`` and ``_bootstrap`` commit. Under the default join
    mode a session ``rollback()`` would discard the test's *outer* transaction,
    so the service's commit and rollback are made to behave as in production
    while the outer transaction still discards everything afterwards.
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
    system_ids = select(models.User.id).where(models.User.is_system.is_(True))
    # ``recipe_tag`` does not cascade from ``recipes``, so the import-time
    # catalog's tag links go first; everything else cascades from the account.
    db_session.execute(
        delete(models.recipe_tag_table).where(
            models.recipe_tag_table.c.recipe_id.in_(
                select(models.Recipe.id).where(models.Recipe.user_id.in_(system_ids))
            )
        )
    )
    db_session.execute(delete(models.User).where(models.User.id.in_(system_ids)))
    assert db_session.scalar(system_ids.limit(1)) is None

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


def test_a_bad_item_writes_nothing(db_session, system_account, tmp_path):
    """One commit for the whole pack: a failure part-way leaves no half catalog."""
    broken = [PACK[0], {**PACK[1], "ingredients": [{"name": "Salt", "quantity": 1, "unit": "cup"}]}]

    with pytest.raises(ValueError):
        catalog.populate_from_pack(db_session, path=_write_pack(tmp_path, broken))

    assert _entries(db_session) == 0
