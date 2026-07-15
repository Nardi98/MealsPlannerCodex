# tests/conftest.py
import os
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Ensure the repository root is on the Python path when tests are executed via
# the ``pytest`` entrypoint.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from database import Base
import models  # ensures tables are registered

# The suite runs against PostgreSQL for parity with production (Railway). Point
# ``TEST_DATABASE_URL`` at a disposable Postgres database; CI and docker-compose
# provide one. Falls back to a local default matching the compose service.
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://user:pass@localhost:5432/mealsdb_test",
)


@pytest.fixture(scope="session")
def engine():
    eng = create_engine(TEST_DATABASE_URL, future=True)
    # Reset any stale schema from a previous run, then build a clean one.
    Base.metadata.drop_all(bind=eng)
    Base.metadata.create_all(bind=eng)
    return eng

@pytest.fixture
def db_session(engine):
    connection = engine.connect()
    trans = connection.begin()
    TestingSessionLocal = sessionmaker(bind=connection, autoflush=False, autocommit=False, future=True)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        trans.rollback()
        connection.close()


@pytest.fixture
def api_client():
    """A ``TestClient`` on a freshly reset real-engine DB with one logged-in user.

    Route tests that exercise the now per-user recipe/ingredient/tag/feedback
    endpoints need an authenticated caller whose owned rows live in the same DB
    the routes query. This resets the schema, inserts a user, and overrides the
    ``get_current_user`` dependency to return it.
    """
    import auth_users
    import crud
    from main import app
    from database import SessionLocal, engine as app_engine

    Base.metadata.drop_all(bind=app_engine)
    Base.metadata.create_all(bind=app_engine)

    session = SessionLocal()
    try:
        user = crud.create_user(
            session, email="routes@test.local", hashed_password="x"
        )
    finally:
        session.close()

    app.dependency_overrides[auth_users.get_current_user] = lambda: user
    from fastapi.testclient import TestClient

    with TestClient(app) as client:
        client.current_user = user
        yield client
    app.dependency_overrides.clear()
