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
