"""``GET /shared-with-me`` and its dismiss endpoint (§5.3).

The list is the one place where one account reads rows another account owns, so
these tests check the boundary in both directions: what an unverified address
must *not* buy, and what the entry is allowed to say about the sharer.
"""

import json
from datetime import datetime, timedelta

import pytest

import crud
import shares
from conftest import client_as
from main import app


@pytest.fixture
def recipient(db_session):
    """A second account with a *verified* address -- SWM-1's precondition."""
    account = crud.create_user(
        db_session, email="reader@test.local", username="reader",
        hashed_password="x",
    )
    account.email_verified = True
    db_session.flush()
    return account


@pytest.fixture
def client(db_session, recipient):
    """Logged in as the recipient, not the sharer."""
    try:
        yield client_as(db_session, recipient)
    finally:
        app.dependency_overrides.clear()


def _share_to(db_session, recipe, owner, **kwargs):
    kwargs.setdefault("mode", "person")
    share, token = shares.create_share(
        db_session, recipe=recipe, owner=owner, **kwargs
    )
    db_session.flush()
    return share, token


# --- SWM-1 -----------------------------------------------------------------

def test_a_share_naming_my_verified_email_appears(
    client, db_session, make_recipe, user, recipient
):
    recipe = make_recipe("Ragu")
    _share_to(db_session, recipe, user, recipient_email=recipient.email)
    rows = client.get("/shared-with-me").json()
    assert [row["recipe"]["title"] for row in rows] == ["Ragu"]


def test_a_share_naming_my_account_appears(
    client, db_session, make_recipe, user, recipient
):
    recipe = make_recipe("Ragu")
    _share_to(db_session, recipe, user, recipient_user=recipient)
    assert len(client.get("/shared-with-me").json()) == 1


def test_a_share_to_somebody_else_does_not_appear(
    client, db_session, make_recipe, user
):
    _share_to(
        db_session, make_recipe("Ragu"), user, recipient_email="nobody@test.local"
    )
    assert client.get("/shared-with-me").json() == []


def test_a_revoked_share_does_not_appear(client, db_session, make_recipe, user, recipient):
    share, _ = _share_to(
        db_session, make_recipe("Ragu"), user, recipient_email=recipient.email
    )
    shares.revoke_share(db_session, share)
    assert client.get("/shared-with-me").json() == []


def test_an_expired_share_does_not_appear(client, db_session, make_recipe, user, recipient):
    _share_to(
        db_session,
        make_recipe("Ragu"),
        user,
        recipient_email=recipient.email,
        expires_at=datetime.utcnow() - timedelta(seconds=1),
    )
    assert client.get("/shared-with-me").json() == []


# --- SWM-4 -----------------------------------------------------------------

def test_an_unverified_address_grants_nothing(
    client, db_session, make_recipe, user, recipient
):
    recipient.email_verified = False
    db_session.flush()
    _share_to(db_session, make_recipe("Ragu"), user, recipient_email=recipient.email)
    assert client.get("/shared-with-me").json() == []


# --- SWM-3 -----------------------------------------------------------------

def test_dismissing_removes_the_entry_from_my_list(
    client, db_session, make_recipe, user, recipient
):
    share, _ = _share_to(
        db_session, make_recipe("Ragu"), user, recipient_email=recipient.email
    )
    assert client.post(f"/shared-with-me/{share.id}/dismiss").status_code == 204
    assert client.get("/shared-with-me").json() == []


def test_dismissing_leaves_the_share_itself_working(
    client, db_session, make_recipe, user, recipient
):
    recipe = make_recipe("Ragu")
    share, token = _share_to(
        db_session, recipe, user, recipient_email=recipient.email
    )
    client.post(f"/shared-with-me/{share.id}/dismiss")
    db_session.refresh(recipe)
    assert shares.resolve(db_session, token) is not None
    assert recipe.visibility == "unlisted"


def test_dismissing_a_share_addressed_to_somebody_else_is_404(
    client, db_session, make_recipe, user
):
    share, _ = _share_to(
        db_session, make_recipe("Ragu"), user, recipient_email="nobody@test.local"
    )
    assert client.post(f"/shared-with-me/{share.id}/dismiss").status_code == 404


def test_dismissing_a_nonexistent_share_is_the_same_404(
    client, db_session, make_recipe, user
):
    share, _ = _share_to(
        db_session, make_recipe("Ragu"), user, recipient_email="nobody@test.local"
    )
    missing = client.post("/shared-with-me/10000000/dismiss")
    theirs = client.post(f"/shared-with-me/{share.id}/dismiss")
    assert missing.status_code == theirs.status_code == 404
    assert missing.json() == theirs.json()


# --- SWM-2 / SWM-5 / PRV-3 -------------------------------------------------

def test_entries_are_read_only(client, db_session, make_recipe, user, recipient):
    """SWM-2: view and copy are the only verbs; there is no mutating route."""
    share, _ = _share_to(
        db_session, make_recipe("Ragu"), user, recipient_email=recipient.email
    )
    recipe_id = share.recipe_id
    assert client.put(
        f"/recipes/{recipe_id}",
        json={"title": "Hijacked", "course": "main"},
    ).status_code == 404
    assert client.delete(f"/recipes/{recipe_id}").status_code == 404


def test_a_shared_recipe_is_not_in_my_own_recipe_list(
    client, db_session, make_recipe, user, recipient
):
    """SWM-5."""
    _share_to(db_session, make_recipe("Ragu"), user, recipient_email=recipient.email)
    assert client.get("/recipes").json() == []


def test_an_entry_leaks_neither_ids_nor_addresses(
    client, db_session, make_recipe, user, recipient
):
    """PRV-3, SWM-5: the sharer's address and every numeric id stay out."""
    recipe = make_recipe("Ragu")
    _share_to(db_session, recipe, user, recipient_email=recipient.email)
    body = client.get("/shared-with-me").json()
    text = json.dumps(body)
    assert user.email not in text
    assert recipient.email not in text
    assert "user_id" not in text
    assert "recipe_id" not in text
    assert "score" not in text
    assert body[0]["recipe"]["author_username"] == user.username
