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
from contextlib import contextmanager
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
    with _scratch_database() as (config, url):
        upgrade(config, "head")
        engine = sa.create_engine(url)
        try:
            yield engine
        finally:
            engine.dispose()


@contextmanager
def _scratch_database():
    """A throwaway database and an alembic config aimed at it."""
    admin = sa.create_engine(
        _with_database(TEST_DATABASE_URL, "postgres"), isolation_level="AUTOCOMMIT"
    )
    with admin.connect() as conn:
        conn.execute(
            sa.text(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                f"WHERE datname = '{SCRATCH_DB}'"
            )
        )
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
        yield config, url
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


# The revision that narrowed the stored vocabulary. Everything before it could
# store a quantity in kg or l; nothing after it can.
BEFORE_DIMENSIONS = "2ca32a5d0e51"


def test_existing_kg_and_l_quantities_are_rewritten_into_base_units():
    """An account's stored amounts survive the vocabulary narrowing.

    ``2 kg`` and ``2 kilograms written as 2000 g`` are the same amount, so the
    migration must multiply as it rewrites the unit. Getting this backwards
    would silently shrink every shopping list by a factor of a thousand.
    """
    with _scratch_database() as (config, url):
        upgrade(config, BEFORE_DIMENSIONS)

        engine = sa.create_engine(url)
        with engine.begin() as conn:
            conn.execute(
                sa.text(
                    "INSERT INTO users (id, email, username, auth_provider, "
                    "created_at, default_people, email_verified) VALUES "
                    "(1, 'a@b.c', 'ab', 'local', now(), 2, true)"
                )
            )
            conn.execute(
                sa.text(
                    "INSERT INTO recipes (id, title, course, user_id, servings) "
                    "VALUES (1, 'Stew', 'MAIN', 1, 1)"
                )
            )
            conn.execute(
                sa.text(
                    "INSERT INTO ingredients (id, name, user_id, unit) VALUES "
                    "(1, 'Rice', 1, 'KG'), (2, 'Stock', 1, 'L'), "
                    "(3, 'Salt', 1, 'G')"
                )
            )
            conn.execute(
                sa.text(
                    "INSERT INTO recipe_ingredients "
                    "(recipe_id, ingredient_id, quantity, unit) VALUES "
                    "(1, 1, 2, 'KG'), (1, 2, 1.5, 'L'), (1, 3, 20, 'G')"
                )
            )
        engine.dispose()

        upgrade(config, "head")

        engine = sa.create_engine(url)
        with engine.connect() as conn:
            rows = conn.execute(
                sa.text(
                    "SELECT ingredient_id, quantity, unit FROM "
                    "recipe_ingredients ORDER BY ingredient_id"
                )
            ).all()
        engine.dispose()

    assert rows == [(1, 2000.0, "G"), (2, 1500.0, "ML"), (3, 20.0, "G")]


def test_the_narrowed_vocabulary_is_enforced_by_the_database():
    """After the migration the database itself refuses a non-base unit."""
    with _scratch_database() as (config, url):
        upgrade(config, "head")
        engine = sa.create_engine(url)
        with engine.connect() as conn:
            members = conn.execute(
                sa.text(
                    "SELECT enumlabel FROM pg_enum e JOIN pg_type t "
                    "ON t.oid = e.enumtypid WHERE t.typname = 'unit_enum' "
                    "ORDER BY e.enumsortorder"
                )
            ).scalars().all()
        engine.dispose()

    assert members == ["G", "ML", "PIECE"]
