"""UN-1/UN-2/UN-3: the ``users.username`` column and its normalisation.

Constraint-level tests only. The availability endpoint and the change flow are
built in later phases.
"""

import pytest
from sqlalchemy import select

import crud
from models import User


def test_username_is_lowercased_on_assignment(db_session):
    """UN-3: input is folded rather than rejected for case."""
    user = User(email="mixed@x.test", username="MixedCase", hashed_password="x")
    assert user.username == "mixedcase"

    user.username = "ANOTHER_ONE"
    assert user.username == "another_one"


def test_username_is_not_nullable(db_session):
    """UN-1: a user with no handle cannot be persisted."""
    db_session.add(User(email="nohandle@x.test", hashed_password="x"))
    with pytest.raises(Exception):
        db_session.flush()
    db_session.rollback()


def test_username_uniqueness_is_case_insensitive(db_session):
    """UN-2: enforced by ``uq_user_username_lower``, not by app code."""
    db_session.add(User(email="a@x.test", username="chef", hashed_password="x"))
    db_session.flush()
    # The validator lowercases, so the collision is only reachable through the
    # functional index -- which is exactly what UN-2 asks for.
    db_session.add(User(email="b@x.test", username="CHEF", hashed_password="x"))
    with pytest.raises(Exception):
        db_session.flush()
    db_session.rollback()


def test_username_changed_at_defaults_to_null(db_session):
    """D-7: NULL means "system-assigned, unconfirmed"."""
    user = User(email="prov@x.test", username="prov", hashed_password="x")
    db_session.add(user)
    db_session.flush()
    assert user.username_changed_at is None


def test_create_user_derives_a_handle_from_the_email(db_session):
    user = crud.create_user(db_session, email="Anna.Rossi@example.com")
    assert user.username == "anna_rossi"
    # System-assigned, so the account still has to confirm it (D-7).
    assert user.username_changed_at is None


def test_create_user_disambiguates_a_taken_handle(db_session):
    first = crud.create_user(db_session, email="anna.rossi@example.com")
    second = crud.create_user(db_session, email="anna.rossi@other.example")
    assert first.username == "anna_rossi"
    assert second.username == "anna_rossi2"


def test_create_user_avoids_reserved_handles(db_session):
    import usernames

    usernames.seed_reserved(db_session)
    user = crud.create_user(db_session, email="admin@example.com")
    assert user.username != "admin"
    assert user.username.startswith("admin")


def test_create_user_pads_a_too_short_local_part(db_session):
    """UN-3 requires at least three characters."""
    user = crud.create_user(db_session, email="jo@example.com")
    assert len(user.username) >= 3


def test_create_user_accepts_an_explicit_username(db_session):
    user = crud.create_user(
        db_session, email="explicit@example.com", username="Cucina_Mia"
    )
    assert user.username == "cucina_mia"
    stored = db_session.execute(
        select(User).where(User.email == "explicit@example.com")
    ).scalar_one()
    assert stored.username == "cucina_mia"
