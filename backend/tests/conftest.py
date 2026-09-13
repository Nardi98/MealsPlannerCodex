# tests/conftest.py
import os
import sys
from pathlib import Path

import pytest
from sqlalchemy.orm import sessionmaker

# Ensure the repository root is on the Python path when tests are executed via
# the ``pytest`` entrypoint.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# The suite runs against PostgreSQL for parity with production (Railway). Point
# ``TEST_DATABASE_URL`` at a disposable Postgres database -- the schema is dropped
# and rebuilt, so never aim it at one holding real data. CI provides one; the
# default matches CI's.
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://user:pass@localhost:5432/mealsdb_test",
)

# ``database`` resolves DATABASE_URL at import time and has no fallback, so it
# must be set before the import below (hence the ``noqa: E402``). Assign rather
# than ``setdefault``: these tests drop every table, so an ambient DATABASE_URL
# pointing at a real database must never win over TEST_DATABASE_URL.
os.environ["DATABASE_URL"] = TEST_DATABASE_URL

# ``auth_users`` fails closed when JWT_SECRET is unset (mirrors DATABASE_URL), so
# the suite must supply one before importing anything that imports it.
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production")
# The auth rate limiter uses process-wide in-memory counters; leaving it on
# would let calls from one test throttle another. Tests that exercise the limit
# re-enable it explicitly.
os.environ["RATE_LIMIT_ENABLED"] = "0"

from database import Base, engine as _app_engine  # noqa: E402
import models  # noqa: E402  ensures tables are registered


def reset_schema(bind):
    """Drop and rebuild every table on ``bind``.

    The whole suite shares one Postgres database, so any test that *commits*
    (rather than relying on ``db_session``'s rollback) must call this afterwards
    or its rows leak into unrelated tests.
    """
    Base.metadata.drop_all(bind=bind)
    Base.metadata.create_all(bind=bind)


# Build the schema at import time, before any test module runs
# ``from main import app``: the app's startup bootstrap queries tables, and the
# app no longer creates them itself. Built from the models rather than by
# running Alembic so the suite stays fast; ``tests/test_migrations.py`` is what
# checks the migrations still agree with them.
reset_schema(_app_engine)


@pytest.fixture(scope="session")
def engine():
    """The application's own engine, pointed at ``TEST_DATABASE_URL`` above.

    Reusing it rather than building a second one keeps the suite on a single
    connection pool -- two pools on one database means ``reset_schema``'s
    ``DROP TABLE`` can block on connections the other pool is holding.

    The schema was already built at import time above; this only hands the
    engine to the tests that ask for it.
    """
    return _app_engine

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
def user(db_session):
    """A persisted account to own the rows a test creates.

    Plans are per-user (``meal_plans.user_id`` is not nullable), so any test
    touching a :class:`MealPlan` needs a real owner.
    """
    import crud

    return crud.create_user(
        db_session,
        email="owner@test.local",
        username="owner",
        hashed_password="x",
    )


@pytest.fixture
def other_user(db_session):
    """A second persisted account, for cross-user and sharing tests.

    Every requirement in §5 and §7 is about two people, so the second account is
    a fixture rather than something each test hand-rolls.
    """
    import crud

    return crud.create_user(
        db_session,
        email="other@test.local",
        username="other",
        hashed_password="x",
    )


@pytest.fixture
def make_recipe(db_session, user):
    """Factory for a persisted recipe owned by the ``user`` fixture."""
    import crud

    def _make(title, course="main", **overrides):
        return crud.create_recipe(
            db_session,
            title=title,
            course=course,
            user_id=user.id,
            **overrides,
        )

    return _make


@pytest.fixture
def system_account(db_session):
    """The ``is_system`` account, with an empty catalog for this test.

    From T8 onward ``main._bootstrap`` loads the catalog pack into the test DB at
    import time, so a catalog test cannot assume it starts from nothing. The
    entries are cleared here, inside the test's rolled-back transaction, which
    is what lets catalog tests assert on exactly the rows they created.
    """
    import catalog
    from sqlalchemy import delete

    account = catalog.ensure_system_account(db_session)
    db_session.execute(delete(models.CatalogEntry))
    return account


@pytest.fixture
def make_catalog_recipe(db_session, system_account):
    """Factory for a system-owned recipe with a catalog entry.

    Inserts the rows directly rather than through ``catalog.publish`` so tests
    of the service are not built on the service. Ingredient and tag names are
    resolved in the system account's namespace, as every catalog recipe's are.
    """
    from datetime import datetime

    import crud

    def _make(
        title,
        course="main",
        status="published",
        ingredients=(("Pasta", 80, "g"),),
        tags=("pasta",),
        procedure="Cook it.",
        bulk_prep=False,
        servings=1,
    ):
        recipe = models.Recipe(
            user_id=system_account.id,
            title=title,
            course=course,
            procedure=procedure,
            bulk_prep=bulk_prep,
            servings=servings,
        )
        for name, quantity, unit in ingredients:
            ingredient = crud.get_or_create_ingredient(
                db_session, None, name, system_account.id
            )
            recipe.ingredients.append(
                models.RecipeIngredient(
                    ingredient=ingredient, quantity=quantity, unit=models.UnitEnum(unit)
                )
            )
        for name in tags:
            recipe.tags.append(crud.get_or_create_tag(db_session, name, system_account.id))
        recipe.catalog_entry = models.CatalogEntry(
            status=status,
            retired_at=datetime.utcnow() if status == "retired" else None,
        )
        db_session.add(recipe)
        db_session.flush()
        return recipe

    return _make


@pytest.fixture
def admin_user(db_session):
    """An account with ``is_admin`` set.

    Test-only. ADM-2: nothing in the application writes ``is_admin`` -- it is
    granted by SQL alone -- so a test needing an admin sets it directly here.
    """
    import crud

    account = crud.create_user(
        db_session,
        email="admin@test.local",
        username="admin_account",
        hashed_password="x",
    )
    account.is_admin = True
    db_session.flush()
    return account


def db_client(session):
    """Return a ``TestClient`` reading ``session`` with nobody logged in.

    The counterpart of :func:`client_as`, for tests that exercise the
    unauthenticated path. Callers are responsible for
    ``app.dependency_overrides.clear()``.
    """
    from fastapi.testclient import TestClient
    from main import app, get_db

    def _db():
        yield session

    app.dependency_overrides[get_db] = _db
    return TestClient(app)


def client_as(session, user):
    """Return a ``TestClient`` reading ``session`` and logged in as ``user``.

    The overrides are global to ``app``, so calling this again re-points the
    client at a different account — which is how the cross-user isolation tests
    switch identities mid-test. Callers are responsible for
    ``app.dependency_overrides.clear()``; the :func:`auth_client` fixture does
    it for the single-user case.
    """
    import auth_users
    from main import app

    client = db_client(session)
    app.dependency_overrides[auth_users.get_current_user] = lambda: user
    return client


@pytest.fixture
def auth_client(db_session, user):
    """A ``TestClient`` reading ``db_session`` and logged in as ``user``.

    Unlike :func:`api_client` this shares the test's transaction, so rows the
    test creates via ``db_session`` are visible to the routes and are rolled
    back afterwards.
    """
    from main import app

    try:
        yield client_as(db_session, user)
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def anon(db_session):
    """A ``TestClient`` on ``db_session`` with nobody logged in.

    The unauthenticated counterpart of :func:`auth_client`, and the fixture
    every "can a stranger reach this" test needs. Lives here because six files
    had already hand-rolled the identical three lines, and a shared override
    that some tests forget to clear is a cross-test contamination bug waiting
    to happen -- the ``finally`` below is the point of wrapping it at all.
    """
    from main import app

    try:
        yield db_client(db_session)
    finally:
        app.dependency_overrides.clear()


def get_route_paths(app, *, parameterised: bool = True) -> list[str]:
    """Every GET path registered on ``app``, sorted and de-duplicated.

    The sweep tests (``test_forward_compat``, ``test_private_unreachable``,
    ``test_provisional_handle_exposure``) all walk the routing table asking
    "and what about this one too?", which is the only way to write an assertion
    that covers routes nobody has added yet. They need the same list, so it is
    built once here.

    ``parameterised=False`` drops paths containing ``{...}``, for callers that
    fetch each path as-is rather than substituting ids into it.
    """
    paths = set()
    for route in app.routes:
        methods = getattr(route, "methods", None) or set()
        path = getattr(route, "path", "")
        if not path or "GET" not in methods:
            continue
        if not parameterised and "{" in path:
            continue
        paths.add(path)
    return sorted(paths)


@pytest.fixture
def api_client(engine):
    """A ``TestClient`` on the real-engine DB with one logged-in user.

    Route tests that exercise the now per-user recipe/ingredient/tag/feedback
    endpoints need an authenticated caller whose owned rows live in the same DB
    the routes query. This inserts a user and overrides the ``get_current_user``
    dependency to return it.

    Unlike :func:`auth_client` this commits, so it resets the schema on the way
    out; the schema is already clean on the way in (the ``engine`` fixture builds
    it, and every committing test cleans up after itself).
    """
    import auth_users
    import crud
    from main import app
    from database import SessionLocal

    session = SessionLocal()
    try:
        user = crud.create_user(
            session,
            email="routes@test.local",
            username="routes",
            hashed_password="x",
        )
    finally:
        session.close()

    app.dependency_overrides[auth_users.get_current_user] = lambda: user
    from fastapi.testclient import TestClient

    try:
        with TestClient(app) as client:
            client.current_user = user
            yield client
    finally:
        app.dependency_overrides.clear()
        reset_schema(engine)
