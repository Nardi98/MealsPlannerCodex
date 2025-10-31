import importlib.util
import uuid
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


def test_migration_adds_course_default(engine):
    schema = f"migration_{uuid.uuid4().hex}"

    with engine.connect() as connection:
        connection = connection.execution_options(isolation_level="AUTOCOMMIT")
        connection.execute(sa.text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        connection.execute(sa.text(f'CREATE SCHEMA "{schema}"'))

    try:
        with engine.begin() as conn:
            conn.execute(sa.text(f'SET search_path TO "{schema}"'))
            conn.execute(
                sa.text(
                    "CREATE TABLE recipes ("
                    "id SERIAL PRIMARY KEY, "
                    "title VARCHAR NOT NULL, "
                    "servings_default INTEGER NOT NULL"
                    ")"
                )
            )
            conn.execute(
                sa.text("INSERT INTO recipes (title, servings_default) VALUES ('Soup', 1)")
            )

        migrations_dir = Path(__file__).resolve().parent.parent / "migrations"
        migration_file = sorted(migrations_dir.glob("003*.py"))[0]
        spec = importlib.util.spec_from_file_location("migration", migration_file)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)

        with engine.begin() as conn:
            conn.execute(sa.text(f'SET search_path TO "{schema}"'))
            ctx = MigrationContext.configure(conn)
            op = Operations(ctx)
            migration.op = op
            migration.upgrade()

        with engine.connect() as conn:
            conn.execute(sa.text(f'SET search_path TO "{schema}"'))
            result = conn.execute(sa.text("SELECT course FROM recipes")).fetchone()
        assert result[0] == "main"
    finally:
        with engine.connect() as connection:
            connection = connection.execution_options(isolation_level="AUTOCOMMIT")
            connection.execute(sa.text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))

