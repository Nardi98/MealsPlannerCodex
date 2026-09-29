"""The testing seed must leave one open import batch to review.

CLAUDE.md makes updating ``seed_testing_data.py`` part of any schema change;
these assertions are the executable form of that rule for the import staging
tables. The batch is deliberately *open* -- it holds unfinished items -- so a
``docker compose up`` lands on a database where the review page has something
to render.
"""

from sqlalchemy import select

import catalog_import
from models import CatalogImportBatch, CatalogImportItem, Recipe, User
from scripts.seed_testing_data import populate


def _batch(session) -> CatalogImportBatch:
    return session.execute(select(CatalogImportBatch)).scalars().one()


def test_the_seed_creates_one_batch_owned_by_the_admin(db_session):
    populate(db_session)

    batch = _batch(db_session)
    admin = db_session.get(User, batch.created_by_user_id)
    assert admin.is_admin is True
    assert batch.filename.endswith(".json")


def test_the_batch_holds_a_pending_an_invalid_and_a_duplicate_item(db_session):
    populate(db_session)

    items = _batch(db_session).items
    assert [item.position for item in items] == list(range(len(items)))

    by_state = {}
    for item in items:
        by_state.setdefault(item.state, []).append(item)

    assert len(by_state["pending"]) >= 2
    invalid = by_state["invalid"]
    assert len(invalid) == 1
    # An invalid entry says why -- and says it in the words the real staging
    # path produces, so the seed cannot ship an error the app never generates.
    assert invalid[0].error == catalog_import._entry_problem(invalid[0].source)

    duplicates = [item for item in items if item.duplicate_recipe_id is not None]
    assert len(duplicates) == 1
    existing = db_session.get(Recipe, duplicates[0].duplicate_recipe_id)
    # The flag points at the catalog recipe that already carries that title.
    assert existing.title == duplicates[0].draft["title"]
    assert duplicates[0].state == "pending"


def test_every_item_keeps_its_source_untouched(db_session):
    populate(db_session)

    for item in _batch(db_session).items:
        assert item.source is not None
        assert item.committed_recipe_id is None


def test_pruning_the_batch_removes_its_items(db_session):
    """The FK cascade the auto-delete relies on, exercised on seeded rows."""
    populate(db_session)

    batch = _batch(db_session)
    db_session.delete(batch)
    db_session.flush()
    assert db_session.execute(select(CatalogImportItem)).scalars().all() == []
