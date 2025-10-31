# tests/conftest.py
import os
import sys
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Ensure the repository root is on the Python path when tests are executed via
# the ``pytest`` entrypoint.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mealplanner.db import Base
from mealplanner import models  # noqa: F401  # ensures tables are registered

_POSTGRES_PREFIXES = (
    "postgresql://",
    "postgresql+psycopg2://",
    "postgresql+psycopg://",
)


@pytest.fixture(scope="session")
def engine():
    database_url = os.environ.get("DATABASE_URL", "").strip()
    if not database_url or not database_url.startswith(_POSTGRES_PREFIXES):
        raise RuntimeError(
            "Tests require DATABASE_URL to point to a PostgreSQL-compatible database."
        )

    schema = os.environ.get("TEST_DATABASE_SCHEMA") or f"test_{uuid.uuid4().hex}"

    eng = create_engine(database_url, future=True)
    eng.info["test_schema"] = schema

    # Prepare a clean schema for the test session.
    with eng.connect() as conn:
        conn = conn.execution_options(isolation_level="AUTOCOMMIT")
        conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        conn.execute(text(f'CREATE SCHEMA "{schema}"'))

    with eng.begin() as conn:
        conn.execute(text(f'SET search_path TO "{schema}"'))
        Base.metadata.create_all(bind=conn)

    try:
        yield eng
    finally:
        with eng.connect() as conn:
            conn = conn.execution_options(isolation_level="AUTOCOMMIT")
            conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        eng.dispose()


@pytest.fixture
def db_session(engine):
    connection = engine.connect()
    schema = engine.info.get("test_schema")
    if schema:
        connection.execute(text(f'SET search_path TO "{schema}"'))
    trans = connection.begin()
    TestingSessionLocal = sessionmaker(bind=connection, autoflush=False, autocommit=False, future=True)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        trans.rollback()
        connection.close()
