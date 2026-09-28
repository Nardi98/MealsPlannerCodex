"""The staging tables behind the reviewed catalog import.

A batch has no status column -- its state is derivable from its items -- so
these tests pin the item states and the cascade that makes an abandoned batch
take its items with it.
"""

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError

import models


def _system(db_session):
    import catalog

    return catalog.ensure_system_account(db_session)


def _batch(db_session, user, **kwargs):
    batch = models.CatalogImportBatch(
        created_by_user_id=user.id, filename="pack.json", **kwargs
    )
    db_session.add(batch)
    db_session.flush()
    return batch


def test_batch_columns():
    """A batch records who uploaded what, and when -- nothing else."""
    columns = {c.name for c in inspect(models.CatalogImportBatch).columns}
    assert columns == {"id", "created_by_user_id", "filename", "created_at"}


def test_item_columns():
    """An item keeps the uploaded entry, the working copy and its outcome."""
    columns = {c.name for c in inspect(models.CatalogImportItem).columns}
    assert columns == {
        "id",
        "batch_id",
        "position",
        "source",
        "draft",
        "state",
        "error",
        "committed_recipe_id",
        "duplicate_recipe_id",
    }


def test_item_defaults_to_pending(db_session, user):
    batch = _batch(db_session, user)
    item = models.CatalogImportItem(
        batch=batch, position=0, source={"title": "Soup"}, draft={"title": "Soup"}
    )
    db_session.add(item)
    db_session.flush()
    assert item.state == "pending"
    assert item.error is None
    assert item.committed_recipe_id is None
    assert item.duplicate_recipe_id is None


def test_item_state_is_constrained(db_session, user):
    """Only the four states the review flow knows about are storable."""
    batch = _batch(db_session, user)
    db_session.add(
        models.CatalogImportItem(
            batch=batch, position=0, source={}, draft={}, state="halfway"
        )
    )
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_remove_system_catalog_clears_staged_imports(db_session, user):
    """Staging is part of the catalog's state, so the reset must take it too.

    An item's recipe foreign keys are ``SET NULL``, so rows left behind would
    survive the system account silently and leak into unrelated tests.
    """
    from conftest import remove_system_catalog

    batch = _batch(db_session, user)
    db_session.add(
        models.CatalogImportItem(batch=batch, position=0, source={}, draft={})
    )
    db_session.flush()

    remove_system_catalog(db_session)
    db_session.flush()

    assert db_session.query(models.CatalogImportItem).count() == 0
    assert db_session.query(models.CatalogImportBatch).count() == 0


def test_deleting_a_batch_deletes_its_items(db_session, user):
    """A finished batch is pruned; its items must not outlive it."""
    batch = _batch(db_session, user)
    db_session.add(
        models.CatalogImportItem(batch=batch, position=0, source={}, draft={})
    )
    db_session.flush()
    batch_id = batch.id
    db_session.delete(batch)
    db_session.flush()
    remaining = (
        db_session.query(models.CatalogImportItem)
        .filter_by(batch_id=batch_id)
        .count()
    )
    assert remaining == 0
