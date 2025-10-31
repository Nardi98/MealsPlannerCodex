from pathlib import Path
import importlib.util

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

from tests.conftest import TEST_DATABASE_URL, temporary_database


def test_migration_adds_course_default():
    with temporary_database(TEST_DATABASE_URL) as url:
        engine = sa.create_engine(url, future=True, pool_pre_ping=True)
        with engine.connect() as conn:
            if engine.dialect.name == "postgresql":
                create_sql = """
CREATE TABLE recipes (
    id SERIAL PRIMARY KEY,
    title VARCHAR NOT NULL,
    servings_default INTEGER NOT NULL
)
"""
            else:
                create_sql = """
CREATE TABLE recipes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title VARCHAR NOT NULL,
    servings_default INTEGER NOT NULL
)
"""

            conn.execute(sa.text(create_sql))
            insert_sql = sa.text(
                "INSERT INTO recipes (title, servings_default) "
                "VALUES ('Soup', 1)"
            )
            conn.execute(insert_sql)
            conn.commit()

        migrations_dir = Path(__file__).resolve().parent.parent / "migrations"
        migration_file = sorted(migrations_dir.glob("003*.py"))[0]
        spec = importlib.util.spec_from_file_location(
            "migration", migration_file
        )
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)

        with engine.connect() as conn:
            ctx = MigrationContext.configure(conn)
            op = Operations(ctx)
            migration.op = op
            migration.upgrade()
            conn.commit()

        with engine.connect() as conn:
            result = conn.execute(
                sa.text("SELECT course FROM recipes")
            ).fetchone()
            assert result[0] == "main"
        engine.dispose()
