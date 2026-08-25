"""The migrations and the models must not drift apart.

The app no longer creates its own tables: a deployed database is evolved by
``alembic upgrade head``. That makes the migration scripts, not
``Base.metadata``, the definition of the deployed schema -- and a model change
that nobody wrote a migration for is now a change that reaches production as a
column the code expects and the database does not have.

This test is the guard: build a database from the migrations alone, then ask
autogenerate whether anything is still missing. It runs against its own
throwaway database so it cannot disturb the schema the rest of the suite shares.
"""

import os
from urllib.parse import urlsplit, urlunsplit

import pytest
import sqlalchemy as sa
from alembic.autogenerate import compare_metadata
from alembic.command import upgrade
from alembic.config import Config
from alembic.migration import MigrationContext

import models
from conftest import TEST_DATABASE_URL

BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRATCH_DB = "mealsdb_migrations"


def _with_database(url: str, name: str) -> str:
    parts = urlsplit(url)
    return urlunsplit(parts._replace(path=f"/{name}"))


@pytest.fixture
def migrated_engine():
    """A database built purely by ``alembic upgrade head``."""
    admin = sa.create_engine(
        _with_database(TEST_DATABASE_URL, "postgres"), isolation_level="AUTOCOMMIT"
    )
    with admin.connect() as conn:
        conn.execute(sa.text(f'DROP DATABASE IF EXISTS "{SCRATCH_DB}"'))
        conn.execute(sa.text(f'CREATE DATABASE "{SCRATCH_DB}"'))
    admin.dispose()

    url = _with_database(TEST_DATABASE_URL, SCRATCH_DB)
    config = Config(os.path.join(BACKEND_ROOT, "alembic.ini"))
    config.set_main_option("script_location", os.path.join(BACKEND_ROOT, "migrations"))

    # ``migrations/env.py`` builds its own engine from DATABASE_URL, so that is
    # the only way to aim it at the scratch database.
    previous = os.environ["DATABASE_URL"]
    os.environ["DATABASE_URL"] = url
    try:
        upgrade(config, "head")
        engine = sa.create_engine(url)
        try:
            yield engine
        finally:
            engine.dispose()
    finally:
        os.environ["DATABASE_URL"] = previous


def test_migrations_reproduce_the_models_exactly(migrated_engine):
    """A model change with no migration behind it fails here.

    If this fails, generate the missing revision:
    ``alembic revision --autogenerate -m "<what changed>"``, review it, and
    commit it alongside the model change.
    """
    with migrated_engine.connect() as connection:
        context = MigrationContext.configure(
            connection,
            opts={
                "compare_type": True,
                "compare_server_default": True,
                "target_metadata": models.Base.metadata,
            },
        )
        diff = compare_metadata(context, models.Base.metadata)

    assert diff == [], f"models and migrations have drifted: {diff}"
