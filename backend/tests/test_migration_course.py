import sqlalchemy as sa

from tests.conftest import TEST_DATABASE_URL, temporary_database
from migration_runner import upgrade as run_migrations


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

        run_migrations(url)

        with engine.connect() as conn:
            result = conn.execute(
                sa.text("SELECT course FROM recipes")
            ).fetchone()
            assert result[0] == "main"
        engine.dispose()
