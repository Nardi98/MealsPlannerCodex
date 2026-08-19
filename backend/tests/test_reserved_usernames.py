"""UN-3/UN-4: username validation and the reserved-handle table."""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

import crud
import usernames
from models import RESERVED_USERNAMES, ReservedUsername


def test_normalise_folds_case_and_trims():
    assert usernames.normalise("  ChefAnna  ") == "chefanna"
    assert usernames.normalise(None) == ""


@pytest.mark.parametrize(
    "value",
    ["abc", "chef_anna", "a_b_c", "user123", "a" * 30],
)
def test_validate_accepts_conforming_handles(value):
    assert usernames.validate(value) == value


@pytest.mark.parametrize(
    "value",
    [
        "ab",              # too short
        "a" * 31,          # too long
        "_leading",        # leading underscore
        "trailing_",       # trailing underscore
        "double__under",   # consecutive underscores
        "has-dash",        # outside the charset
        "has space",
        "accènted",
        "UPPER",           # not normalised by the caller
    ],
)
def test_validate_rejects_non_conforming_handles(value):
    with pytest.raises(ValueError) as exc:
        usernames.validate(value)
    # The message is user-facing, so it must say something.
    assert str(exc.value)


def test_seed_reserved_inserts_the_un4_list(db_session):
    usernames.seed_reserved(db_session)
    stored = {
        row.username
        for row in db_session.execute(select(ReservedUsername)).scalars()
    }
    assert set(RESERVED_USERNAMES) <= stored
    # UN-4 explicitly names these root segments.
    assert {"r", "s", "api", "static", "assets", "admin", "me"} <= stored


def test_seed_reserved_is_idempotent(db_session):
    usernames.seed_reserved(db_session)
    before = len(
        db_session.execute(select(ReservedUsername)).scalars().all()
    )
    usernames.seed_reserved(db_session)
    after = len(db_session.execute(select(ReservedUsername)).scalars().all())
    assert before == after


def test_reserved_handles_are_unavailable(db_session):
    usernames.seed_reserved(db_session)
    assert usernames.is_available(db_session, "admin") is False
    assert usernames.is_available(db_session, "ADMIN") is False
    assert usernames.is_available(db_session, "static") is False


def test_a_free_handle_is_available(db_session):
    usernames.seed_reserved(db_session)
    assert usernames.is_available(db_session, "cucina_mia") is True


def test_a_taken_handle_is_unavailable_case_insensitively(db_session):
    crud.create_user(db_session, email="x@x.test", username="cucina_mia")
    assert usernames.is_available(db_session, "Cucina_Mia") is False


def test_an_expired_reservation_frees_the_handle(db_session):
    """UN-9's release window: a reservation past ``reserved_until`` is spent."""
    usernames.reserve(
        db_session,
        "oldname",
        reason="released",
        reserved_until=datetime.utcnow() - timedelta(days=1),
    )
    assert usernames.is_available(db_session, "oldname") is True


def test_a_live_reservation_holds_the_handle(db_session):
    usernames.reserve(
        db_session,
        "oldname",
        reason="released",
        reserved_until=datetime.utcnow() + timedelta(days=30),
    )
    assert usernames.is_available(db_session, "oldname") is False


def test_reserve_is_idempotent(db_session):
    usernames.reserve(db_session, "dupe")
    usernames.reserve(db_session, "dupe")
    rows = db_session.execute(
        select(ReservedUsername).where(ReservedUsername.username == "dupe")
    ).scalars().all()
    assert len(rows) == 1


def test_an_invalid_handle_is_never_available(db_session):
    assert usernames.is_available(db_session, "has-dash") is False
