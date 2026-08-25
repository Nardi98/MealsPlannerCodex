"""The destructive seed must not be able to wipe a deployed database.

``reset_database`` calls ``Base.metadata.drop_all`` against whatever
``DATABASE_URL`` points at. On Railway that is production, so a single
``railway run python scripts/seed_testing_data.py`` would destroy every tester's
data with no confirmation step. The opt-in env flag makes the destruction
deliberate: local compose sets it, no deployment ever does.
"""

import pytest
import sqlalchemy as sa

from database import Base

from scripts.seed_testing_data import ALLOW_DESTRUCTIVE_SEED_ENV, reset_database


def test_reset_database_refuses_to_run_without_the_flag(monkeypatch):
    monkeypatch.delenv(ALLOW_DESTRUCTIVE_SEED_ENV, raising=False)

    with pytest.raises(RuntimeError) as excinfo:
        reset_database()

    assert ALLOW_DESTRUCTIVE_SEED_ENV in str(excinfo.value)


@pytest.mark.parametrize("value", ["0", "true"])
def test_only_the_exact_opt_in_value_unlocks_the_reset(monkeypatch, value):
    """Anything other than ``1`` is refused.

    A truthy-ish string is exactly the sort of thing that gets left in a
    deployment's variables by accident, so the check is an equality test rather
    than a truthiness test.
    """
    monkeypatch.setenv(ALLOW_DESTRUCTIVE_SEED_ENV, value)

    with pytest.raises(RuntimeError):
        reset_database()


def test_the_flag_allows_the_reset(monkeypatch, engine):
    monkeypatch.setenv(ALLOW_DESTRUCTIVE_SEED_ENV, "1")

    reset_database()

    # Every mapped table is present again, so the reset ran to completion and
    # the rest of the suite still has a schema to work against.
    present = set(sa.inspect(engine).get_table_names())
    assert set(Base.metadata.tables).issubset(present)
