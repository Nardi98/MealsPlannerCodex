from pathlib import Path
import importlib.util

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


def test_migration_adds_course_default(tmp_path):
    engine = sa.create_engine(f"sqlite:///{tmp_path}/legacy.db")
    conn = engine.connect()
    conn.execute(
        sa.text(
            "CREATE TABLE recipes (id INTEGER PRIMARY KEY, title VARCHAR NOT NULL, servings_default INTEGER NOT NULL)"
        )
    )
    conn.execute(
        sa.text("INSERT INTO recipes (title, servings_default) VALUES ('Soup', 1)")
    )
    conn.commit()

    migrations_dir = Path(__file__).resolve().parent.parent / "migrations"
    migration_file = sorted(migrations_dir.glob("003*.py"))[0]
    spec = importlib.util.spec_from_file_location("migration", migration_file)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    ctx = MigrationContext.configure(conn)
    op = Operations(ctx)
    migration.op = op
    migration.upgrade()
    conn.commit()

    result = conn.execute(sa.text("SELECT course FROM recipes")).fetchone()
    assert result[0] == "main"

