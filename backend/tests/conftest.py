import os
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Tuple
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


def _noop() -> None:
    """No-op cleanup callback used for in-memory databases."""
    return None


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _default_database_url() -> str:
    return os.environ.get(
        "TEST_DATABASE_URL",
        (
            "postgresql+psycopg2://postgres:postgres@localhost:5432/"
            "mealplanner_test"
        ),
    )


def _admin_engine(url: URL):
    return create_engine(
        url.set(database="postgres"), future=True, isolation_level="AUTOCOMMIT"
    )


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
            drop_sql = text(
                f"DROP DATABASE IF EXISTS {quote(url.database)} WITH (FORCE)"
            )
            conn.execute(drop_sql)
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


def _can_use_postgres(url: URL) -> bool:
    if not url.drivername.startswith("postgresql"):
        return False
    try:
        engine = _admin_engine(url)
        with engine.connect():
            return True
    except (OperationalError, ModuleNotFoundError, ImportError):
        return False
    finally:
        try:
            engine.dispose()
        except UnboundLocalError:  # pragma: no cover - defensive cleanup
            pass


def _prepare_sqlite_url(url: URL) -> Tuple[str, Callable[[], None]]:
    if url.database in (None, "", ":memory:"):
        return "sqlite+pysqlite:///:memory:", _noop

    if url.database:
        # Convert to absolute path so the cleanup hook can remove it reliably.
        if not Path(url.database).is_absolute():
            tmp_dir = Path(tempfile.gettempdir())
            db_path = tmp_dir / url.database
        else:
            db_path = Path(url.database)
    else:
        tmp_dir = Path(tempfile.gettempdir())
        db_path = tmp_dir / f"{uuid4().hex}.db"

    db_path.parent.mkdir(parents=True, exist_ok=True)
    sqlite_url = url.set(database=str(db_path))

    def _cleanup() -> None:
        try:
            db_path.unlink()
        except FileNotFoundError:  # pragma: no cover - defensive cleanup
            pass

    return str(sqlite_url), _cleanup


def _prepare_database_url(base_url: str) -> Tuple[str, Callable[[], None]]:
    url = make_url(base_url)
    if _can_use_postgres(url):
        def _cleanup_postgres() -> None:
            _drop_database(url)

        return str(url), _cleanup_postgres

    if url.drivername.startswith("postgresql"):
        # Fall back to an in-memory SQLite database when the configured
        # Postgres instance is unavailable.
        sqlite_path = Path(tempfile.gettempdir()) / f"mealplanner_test_{uuid4().hex}.db"
        sqlite_url = make_url(f"sqlite+pysqlite:///{sqlite_path}")
        return _prepare_sqlite_url(sqlite_url)

    if url.drivername.startswith("sqlite"):
        return _prepare_sqlite_url(url)

    raise RuntimeError(
        "Unsupported TEST_DATABASE_URL; provide postgres or sqlite "
        "connection string"
    )


_BASE_TEST_DATABASE_URL = _default_database_url()
(
    _RESOLVED_TEST_DATABASE_URL,
    _BASE_CLEANUP,
) = _prepare_database_url(_BASE_TEST_DATABASE_URL)
TEST_DATABASE_URL = _RESOLVED_TEST_DATABASE_URL
os.environ["DATABASE_URL"] = TEST_DATABASE_URL

import mealplanner.models  # noqa: E402,F401
from mealplanner.db import Base  # noqa: E402
from migration_runner import upgrade as run_migrations  # noqa: E402
from sqlalchemy import text


@contextmanager
def temporary_database(base_url: str):
    url = make_url(base_url)
    if url.drivername.startswith("postgresql") and _can_use_postgres(url):
        db_name = f"{url.database}_{uuid4().hex}"
        temp_url = url.set(database=db_name)
        _create_database(temp_url)
        try:
            yield str(temp_url)
        finally:
            _drop_database(temp_url)
        return

    if url.drivername.startswith("sqlite"):
        temp_path = Path(tempfile.gettempdir()) / f"{uuid4().hex}.db"
        temp_url = url.set(database=str(temp_path))
        try:
            yield str(temp_url)
        finally:
            try:
                temp_path.unlink()
            except FileNotFoundError:  # pragma: no cover - defensive cleanup
                pass
        return

    raise RuntimeError(
        "temporary_database only supports postgres or sqlite URLs in "
        "tests"
    )


@pytest.fixture(scope="session")
def engine():
    url = make_url(TEST_DATABASE_URL)
    cleanup: Callable[[], None]
    if url.drivername.startswith("postgresql"):
        _create_database(url)

        def cleanup() -> None:
            _drop_database(url)
        engine_kwargs = {"future": True, "pool_pre_ping": True}
    else:
        cleanup = _BASE_CLEANUP or _noop
        engine_kwargs = {
            "future": True,
            "pool_pre_ping": True,
            "connect_args": {"check_same_thread": False},
        }
        if url.database in (None, "", ":memory:"):
            engine_kwargs["poolclass"] = StaticPool

    eng = create_engine(str(url), **engine_kwargs)
    run_migrations(eng)
    yield eng
    eng.dispose()
    cleanup()


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
        if engine.dialect.name == "sqlite":
            Base.metadata.drop_all(bind=engine)
            with engine.begin() as conn:
                conn.execute(text("DROP TABLE IF EXISTS alembic_version"))
            run_migrations(engine)
