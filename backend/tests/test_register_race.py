"""Registration's check-then-insert race on the username (UN-2/UN-5).

``POST /auth/register`` asks ``usernames.is_available`` and then inserts. Those
are two statements, and nothing holds a lock between them, so two people
registering ``chef`` at the same moment both pass the check and both try the
insert. ``uq_user_username_lower`` -- a database-level unique index, correctly
placed, because application code cannot win this race -- lets exactly one of
them through and raises ``IntegrityError`` at the other.

Unhandled, that ``IntegrityError`` escapes the handler as a **500**, which is
wrong in three separate ways: it tells the loser the service is broken rather
than that the handle is taken, it leaves the SQLAlchemy session poisoned so no
later statement in the request can run, and a 500 on a registration form is the
kind of thing users report as an outage.

``POST /auth/username`` in ``username_routes`` already solved exactly this, and
its answer is the one adopted here: perform the insert inside a **SAVEPOINT**
so a failure rolls back only the failed assignment and leaves the session
usable, catch ``IntegrityError``, and answer with the *same* 409 and the same
message the pre-check would have produced. The loser cannot tell a race from an
ordinary conflict -- which is right, because their next action is identical
either way: pick another handle.

Determinism
-----------
None of this is tested with threads. A concurrency test that actually races is
a flaky test, and it would prove nothing that this does not: the *only* thing
that distinguishes the racing caller is that the availability check passed and
the insert then failed. Stubbing ``is_available`` to return ``True`` for a
handle that is already taken reproduces precisely that state, every run, in
milliseconds -- the same technique ``test_username_routes`` uses.
"""
from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError

import crud
import usernames
from models import User
from tests.conftest import db_client


@pytest.fixture
def race(monkeypatch):
    """Make every availability check pass, whatever the database says.

    This *is* the race, expressed as a fixture: the losing request is
    definitionally the one whose check said "free" about a handle that was, by
    the time it inserted, taken.
    """
    monkeypatch.setattr(usernames, "is_available", lambda session, candidate: True)


# ---------------------------------------------------------------------------
# the domain layer
# ---------------------------------------------------------------------------
def test_create_user_raises_username_taken_when_the_insert_loses(db_session, race):
    """A domain error, not a raw ``IntegrityError``.

    The route must map this to a 409, and mapping requires being able to tell
    "the handle collided" from "some other constraint broke". Catching
    ``IntegrityError`` at the route and assuming it was the username would turn
    an unrelated constraint failure into a misleading 409.
    """
    crud.create_user(db_session, email="first@test.local", username="chef")

    with pytest.raises(crud.UsernameTaken):
        crud.create_user(db_session, email="second@test.local", username="chef")


def test_the_session_survives_a_lost_race(db_session, race):
    """The SAVEPOINT half of the fix, which is the half that is easy to skip.

    Without ``begin_nested`` the failed ``INSERT`` poisons the session: every
    subsequent statement raises ``PendingRollbackError``, so the handler cannot
    even build its own error response. This asserts the session is still usable
    by doing real work on it afterwards.
    """
    crud.create_user(db_session, email="first@test.local", username="chef")

    with pytest.raises(crud.UsernameTaken):
        crud.create_user(db_session, email="second@test.local", username="chef")

    survivor = crud.create_user(
        db_session, email="third@test.local", username="sous"
    )

    assert survivor.id is not None
    assert db_session.get(User, survivor.id) is not None


def test_a_derived_handle_retries_instead_of_failing(db_session, monkeypatch):
    """The Google / seed-script path must not be able to fail at all.

    A caller who supplied no handle cannot be told "pick another one" -- there
    is nothing for them to pick, and a 409 there would mean Google sign-in
    breaks whenever two people happen to have the same email local part on
    different domains. So the derived path retries with a fresh candidate
    rather than surfacing the conflict.

    ``_derive_username`` is stubbed to keep proposing a taken handle, which is
    what it would genuinely do for the losing request in the real race: it
    checks availability, and the winner had not committed yet.
    """
    crud.create_user(db_session, email="taken@test.local", username="chef")

    proposals = iter(["chef", "chef", "chef2"])
    monkeypatch.setattr(
        crud, "_derive_username", lambda session, email: next(proposals)
    )

    user = crud.create_user(db_session, email="chef@other.local")

    assert user.username == "chef2"


def test_an_unrelated_integrity_error_is_not_disguised_as_a_conflict(
    db_session, race
):
    """Only the username index maps to ``UsernameTaken``.

    A duplicate *email* is a different failure with a different correct
    response (registration's neutral path), and swallowing it as "that username
    is taken" would send the caller chasing the wrong field forever.
    """
    crud.create_user(db_session, email="dup@test.local", username="one")

    with pytest.raises(IntegrityError):
        crud.create_user(db_session, email="dup@test.local", username="two")


# ---------------------------------------------------------------------------
# the route
# ---------------------------------------------------------------------------
def test_register_answers_409_not_500_when_it_loses_the_race(
    db_session, anon, race
):
    """The behaviour the user sees. Same status and wording as a plain conflict."""
    crud.create_user(db_session, email="winner@test.local", username="chef")

    response = anon.post(
        "/auth/register",
        json={
            "email": "loser@example.com",
            "password": "Correct-Horse-Battery9",
            "username": "chef",
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "That username is taken"


def test_the_race_response_is_indistinguishable_from_an_ordinary_conflict(
    db_session, anon, monkeypatch
):
    """SH-27's spirit applied to registration: no oracle for "you lost a race".

    Knowing a conflict was a race rather than a pre-existing account is a small
    but real disclosure -- it says the handle was claimed *just now*. The two
    paths must therefore produce byte-identical answers.
    """
    crud.create_user(db_session, email="winner@test.local", username="chef")

    ordinary = anon.post(
        "/auth/register",
        json={
            "email": "a@example.com",
            "password": "Correct-Horse-Battery9",
            "username": "chef",
        },
    )

    monkeypatch.setattr(usernames, "is_available", lambda session, candidate: True)
    raced = anon.post(
        "/auth/register",
        json={
            "email": "b@example.com",
            "password": "Correct-Horse-Battery9",
            "username": "chef",
        },
    )

    assert ordinary.status_code == raced.status_code == 409
    assert ordinary.json() == raced.json()


def test_no_partial_account_is_left_behind_by_a_lost_race(db_session, anon, race):
    """The rollback, observed from outside.

    ``_create_account`` seeds system tags and a starter ingredient library
    before the conflict surfaces. If the SAVEPOINT were placed wrongly -- or if
    the route committed first and inserted second -- a lost race would leave a
    half-built account with no user row to own it.
    """
    crud.create_user(db_session, email="winner@test.local", username="chef")

    anon.post(
        "/auth/register",
        json={
            "email": "loser@example.com",
            "password": "Correct-Horse-Battery9",
            "username": "chef",
        },
    )

    assert crud.get_user_by_email(db_session, "loser@example.com") is None
