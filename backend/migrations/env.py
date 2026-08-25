"""Alembic environment.

Two things are deliberately *not* configured in ``alembic.ini``: the database
URL and the target metadata. Both are taken from the application itself so
there is exactly one definition of each.

``sqlalchemy.url`` is left empty in the ini file and resolved here through
:func:`database.resolve_database_url`, which is the same function the app uses
-- it requires ``DATABASE_URL`` and normalises a bare ``postgres://`` scheme.
Duplicating that logic in the ini file is how a migration ends up run against a
different database than the one the app is talking to.
"""
import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from sqlalchemy.types import TypeDecorator

from alembic import context

# ``alembic`` is invoked from ``backend/`` but its own package directory is not
# on the path, so the top-level ``database`` / ``models`` modules need help.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database import resolve_database_url  # noqa: E402
import models  # noqa: E402

config = context.config

if config.config_file_name is not None:
    # ``disable_existing_loggers`` defaults to True, which would silence every
    # logger configured before this ran -- including the application's, when a
    # migration is run in-process (the test suite does exactly that).
    fileConfig(config.config_file_name, disable_existing_loggers=False)

config.set_main_option("sqlalchemy.url", resolve_database_url())

# Autogenerate diffs against this. Importing ``models`` above is what registers
# every table on it; without that import the metadata is empty and autogenerate
# would cheerfully propose dropping the entire schema.
target_metadata = models.Base.metadata


def render_item(type_, obj, autogen_context):
    """Render custom column types by their underlying database type.

    ``models.IntList`` and ``models.StrList`` are ``TypeDecorator`` subclasses
    over ``String``: the list-to-CSV conversion is application logic and the column
    is a plain ``VARCHAR``. Without this hook autogenerate emits a literal
    ``models.IntList()`` into the script, which both fails to import and couples
    the migration to a class name the models are free to rename. A migration has
    to keep running unchanged forever, so it may only depend on ``sa`` and
    ``op`` -- never on the application's current model code.

    Matching on ``TypeDecorator`` rather than on the two classes by name means a
    third one added later is handled without anyone having to remember this file.
    """
    if type_ == "type" and isinstance(obj, TypeDecorator):
        return "sa.%r" % obj.impl_instance
    return False


def run_migrations_offline() -> None:
    """Emit SQL to stdout instead of running it, for review or manual apply."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_item=render_item,
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        # ``compare_type`` / ``compare_server_default`` are off by default, which
        # means a column whose type or default changed autogenerates as *no
        # diff at all* -- a silent no-op migration. They are on here so the
        # drift test in ``tests/test_migrations.py`` can actually see drift.
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
            render_item=render_item,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
