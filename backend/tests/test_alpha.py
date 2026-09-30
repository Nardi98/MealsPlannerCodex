"""ALPHA-GATE: tests for the closed-alpha signup allowlist.

Deleted whole when the alpha ends, together with ``alpha.py`` and the
``alpha_invites`` table (see
``docs/superpowers/specs/2026-09-30-alpha-allowlist-design.md``).
"""

from datetime import datetime

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

import alpha
import crud
from models import AlphaInvite, User
from scripts.seed_testing_data import populate


def _count(session) -> int:
    return session.execute(select(func.count()).select_from(AlphaInvite)).scalar_one()


def _add_row(session, email, **kwargs):
    invite = AlphaInvite(email=email, **kwargs)
    session.add(invite)
    session.flush()
    return invite


# --- model -----------------------------------------------------------------


def test_the_model_stores_the_email_normalized(db_session):
    invite = _add_row(db_session, "  Mixed@Case.COM ")

    db_session.expire(invite)
    assert invite.email == "mixed@case.com"


def test_two_invites_for_the_same_address_cannot_coexist(db_session):
    _add_row(db_session, "dupe@x.com")

    with pytest.raises(IntegrityError):
        _add_row(db_session, "DUPE@X.COM")


def test_created_at_is_populated_without_being_passed(db_session):
    invite = _add_row(db_session, "stamped@x.com")

    db_session.refresh(invite)
    assert isinstance(invite.created_at, datetime)


def test_an_invite_need_not_name_who_added_it(db_session):
    invite = _add_row(db_session, "anon@x.com", invited_by_user_id=None)

    assert invite.invited_by_user_id is None


# --- split_emails ----------------------------------------------------------


def test_split_emails_accepts_commas_and_newlines_together():
    assert alpha.split_emails("a@x.com, b@x.com\nc@x.com") == [
        "a@x.com",
        "b@x.com",
        "c@x.com",
    ]


def test_split_emails_drops_blank_lines_and_trailing_separators():
    assert alpha.split_emails("\n a@x.com ,\n\n, b@x.com,\n") == [
        "a@x.com",
        "b@x.com",
    ]


def test_split_emails_deduplicates_by_normalized_form_keeping_the_first():
    assert alpha.split_emails("A@x.com\na@x.com") == ["A@x.com"]


# --- is_valid_email --------------------------------------------------------


def test_is_valid_email_accepts_an_ordinary_address():
    assert alpha.is_valid_email("a@x.com") is True


@pytest.mark.parametrize("value", ["", "nope", "a@", "a b@x.com"])
def test_is_valid_email_rejects_malformed_input(value):
    assert alpha.is_valid_email(value) is False


# --- assert_email_allowed --------------------------------------------------


def test_an_empty_allowlist_leaves_signup_open_to_everyone(db_session):
    """The gate fails open: a fresh or wiped database locks nobody out."""
    assert _count(db_session) == 0

    assert alpha.assert_email_allowed(db_session, "anyone@x.com") is None


def test_a_listed_email_is_allowed(db_session):
    _add_row(db_session, "listed@x.com")

    assert alpha.assert_email_allowed(db_session, "listed@x.com") is None


def test_a_listed_email_is_allowed_whatever_its_case_and_padding(db_session):
    _add_row(db_session, "listed@x.com")

    assert alpha.assert_email_allowed(db_session, "  LISTED@X.COM ") is None


def test_an_unlisted_email_is_refused_with_403(db_session):
    _add_row(db_session, "listed@x.com")

    with pytest.raises(HTTPException) as excinfo:
        alpha.assert_email_allowed(db_session, "stranger@x.com")

    assert excinfo.value.status_code == 403
    assert excinfo.value.detail == alpha.NOT_INVITED_DETAIL


def test_the_refusal_sentence_is_the_one_the_spec_fixes():
    assert alpha.NOT_INVITED_DETAIL == (
        "Meal Planner is in a closed alpha. "
        "This email address hasn't been invited yet."
    )


def test_a_refusal_writes_nothing(db_session):
    _add_row(db_session, "listed@x.com")
    before = _count(db_session)

    with pytest.raises(HTTPException):
        alpha.assert_email_allowed(db_session, "stranger@x.com")

    assert _count(db_session) == before


# --- add_invites -----------------------------------------------------------


def test_add_invites_partitions_new_duplicate_and_invalid(db_session, admin_user):
    _add_row(db_session, "dupe@x.com")
    before = _count(db_session)

    result = alpha.add_invites(
        db_session,
        "new@x.com, dupe@x.com\nnot-an-email\nNEW@x.com",
        invited_by_user_id=admin_user.id,
    )

    assert result.added == ["new@x.com"]
    assert result.skipped_duplicates == ["dupe@x.com"]
    assert result.invalid == ["not-an-email"]
    assert _count(db_session) == before + 1


def test_add_invites_stores_normalized_emails_and_the_inviter(db_session, admin_user):
    alpha.add_invites(
        db_session, " Fresh@X.com ", invited_by_user_id=admin_user.id
    )

    invite = db_session.execute(select(AlphaInvite)).scalar_one()
    assert invite.email == "fresh@x.com"
    assert invite.invited_by_user_id == admin_user.id


def test_add_invites_on_empty_input_writes_nothing(db_session, admin_user):
    result = alpha.add_invites(db_session, "", invited_by_user_id=admin_user.id)

    assert (result.added, result.skipped_duplicates, result.invalid) == ([], [], [])
    assert _count(db_session) == 0


def test_add_invites_commits_at_most_once(db_session, admin_user, monkeypatch):
    calls = []
    real_commit = db_session.commit
    monkeypatch.setattr(
        db_session,
        "commit",
        lambda: (calls.append(1), real_commit())[1],
    )

    alpha.add_invites(
        db_session, "a@x.com\nb@x.com", invited_by_user_id=admin_user.id
    )

    assert len(calls) <= 1


# --- list_invites ----------------------------------------------------------


def test_list_invites_returns_the_newest_first(db_session):
    _add_row(db_session, "older@x.com", created_at=datetime(2026, 1, 1))
    _add_row(db_session, "newer@x.com", created_at=datetime(2026, 2, 1))

    rows = alpha.list_invites(db_session)

    assert [row.invite.email for row in rows] == ["newer@x.com", "older@x.com"]


def test_an_invite_whose_address_has_an_account_reads_as_signed_up(db_session):
    account = crud.create_user(
        db_session,
        email="member@x.com",
        username="member",
        hashed_password="x",
    )
    db_session.flush()
    _add_row(db_session, "member@x.com")

    row = alpha.list_invites(db_session)[0]

    assert row.signed_up is True
    assert row.signed_up_at == account.created_at


def test_an_invite_with_no_account_reads_as_not_signed_up(db_session):
    _add_row(db_session, "pending@x.com")

    row = alpha.list_invites(db_session)[0]

    assert row.signed_up is False
    assert row.signed_up_at is None


def test_a_case_only_difference_still_counts_as_signed_up(db_session):
    crud.create_user(
        db_session,
        email="Member@X.com",
        username="member2",
        hashed_password="x",
    )
    db_session.flush()
    _add_row(db_session, "MEMBER@x.COM")

    assert alpha.list_invites(db_session)[0].signed_up is True


# --- update_note -----------------------------------------------------------


def test_update_note_sets_the_note_and_leaves_the_email_alone(db_session):
    invite = _add_row(db_session, "noted@x.com")

    updated = alpha.update_note(db_session, invite.id, "a friend of a friend")

    assert updated.note == "a friend of a friend"
    assert updated.email == "noted@x.com"


def test_a_blank_note_clears_it(db_session):
    invite = _add_row(db_session, "noted@x.com", note="old")

    assert alpha.update_note(db_session, invite.id, "  ").note is None


def test_update_note_on_a_missing_invite_raises_invite_not_found(db_session):
    with pytest.raises(alpha.InviteNotFound):
        alpha.update_note(db_session, 999999, "x")


# --- delete_invite ---------------------------------------------------------


def test_delete_invite_removes_the_row(db_session):
    invite = _add_row(db_session, "gone@x.com")

    alpha.delete_invite(db_session, invite.id)

    assert db_session.get(AlphaInvite, invite.id) is None


def test_delete_invite_on_a_missing_invite_raises_invite_not_found(db_session):
    with pytest.raises(alpha.InviteNotFound):
        alpha.delete_invite(db_session, 999999)


# --- seed ------------------------------------------------------------------


def test_the_seed_invites_every_account_it_creates(db_session):
    populate(db_session)

    invited = {
        invite.email for invite in db_session.execute(select(AlphaInvite)).scalars()
    }
    for email in db_session.execute(select(User.email)).scalars():
        if email in invited:
            continue
        # The system catalog account never signs up, so it needs no invite.
        account = db_session.execute(
            select(User).where(User.email == email)
        ).scalar_one()
        assert account.is_system, f"{email} is seeded without an invite"


def test_the_seed_leaves_one_invite_without_an_account(db_session):
    """D9: the admin table shows both badges out of the box."""
    populate(db_session)

    emails = set(db_session.execute(select(User.email)).scalars())
    pending = [
        invite.email
        for invite in db_session.execute(select(AlphaInvite)).scalars()
        if invite.email not in emails
    ]
    assert pending
