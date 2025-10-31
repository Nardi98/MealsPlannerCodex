import os
import sys
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TEST_DATABASE_URL = "postgresql+psycopg2://postgres:postgres@localhost:5432/mealplanner_test"
os.environ["DATABASE_URL"] = TEST_DATABASE_URL

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import sessionmaker

from mealplanner.db import Base
from mealplanner import models  # noqa: F401 - ensure models register tables


def _admin_engine(url: URL):
    return create_engine(url.set(database="postgres"), future=True, isolation_level="AUTOCOMMIT")


def _terminate_connections(conn, database: str) -> None:
    conn.execute(
        text(
            "SELECT pg_terminate_backend(pid) "
            "FROM pg_stat_activity "
            "WHERE datname = :name AND pid <> pg_backend_pid()"
        ),
        {"name": database},
    )


def _drop_database(url: URL) -> None:
    if not url.database:
        return
    engine = _admin_engine(url)
    try:
        with engine.connect() as conn:
            quote = conn.dialect.identifier_preparer.quote
            _terminate_connections(conn, url.database)
            conn.execute(text(f"DROP DATABASE IF EXISTS {quote(url.database)} WITH (FORCE)"))
    finally:
        engine.dispose()


def _create_database(url: URL) -> None:
    if not url.database:
        raise RuntimeError("TEST_DATABASE_URL must include a database name")
    _drop_database(url)
    engine = _admin_engine(url)
    try:
        with engine.connect() as conn:
            quote = conn.dialect.identifier_preparer.quote
            conn.execute(text(f"CREATE DATABASE {quote(url.database)}"))
    finally:
        engine.dispose()


@contextmanager
def temporary_database(base_url: str):
    base = make_url(base_url)
    db_name = f"{base.database}_{uuid4().hex}"
    temp_url = base.set(database=db_name)
    _create_database(temp_url)
    try:
        yield str(temp_url)
    finally:
        _drop_database(temp_url)


@pytest.fixture(scope="session")
def engine():
    url = make_url(TEST_DATABASE_URL)
    _create_database(url)
    eng = create_engine(str(url), future=True, pool_pre_ping=True)
    Base.metadata.create_all(bind=eng)
    yield eng
    eng.dispose()
    _drop_database(url)


@pytest.fixture
def db_session(engine):
    connection = engine.connect()
    trans = connection.begin()
    TestingSessionLocal = sessionmaker(
        bind=connection, autoflush=False, autocommit=False, future=True
    )
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        trans.rollback()
        connection.close()
