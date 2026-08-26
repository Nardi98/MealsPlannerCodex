"""View and copy from Shared-with-me, keyed by ``share_id`` (SWM-2).

Tokens are stored as digests only (D-5), so a recipient who no longer holds the
original URL cannot reach the token-keyed routes. These two endpoints close that
gap without ever reconstructing a token: authorisation is membership of the
caller's own active-share list, exactly as the dismiss endpoint decides it.

Because that list is the only key, every way a share can stop being live --
revoked, expired, dismissed, addressed to somebody else, or held by an account
whose address is unverified -- fails closed here for free, and each is asserted
below rather than assumed.
"""

import json
from datetime import datetime, timedelta

import pytest

import crud
import models
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


# ---------------------------------------------------------------------------
# GET /shared-with-me/{share_id}
# ---------------------------------------------------------------------------

def test_i_can_read_one_entry_addressed_to_me(
    client, db_session, make_recipe, user, recipient
):
    """SWM-2: *view* is one of the two permitted actions."""
    share, _ = _share_to(
        db_session, make_recipe("Ragu"), user, recipient_email=recipient.email
    )
    resp = client.get(f"/shared-with-me/{share.id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["share_id"] == share.id
    assert body["recipe"]["title"] == "Ragu"
    assert body["recipe"]["author_username"] == user.username


def test_the_entry_shows_exactly_the_public_allowlist(
    client, db_session, make_recipe, user, recipient
):
    """PRV-2: the same projection the share page uses, no wider."""
    import public_schema

    share, _ = _share_to(
        db_session, make_recipe("Ragu"), user, recipient_email=recipient.email
    )
    body = client.get(f"/shared-with-me/{share.id}").json()
    assert set(body["recipe"]) == set(public_schema.PublicRecipe.model_fields)


def test_the_entry_leaks_neither_ids_nor_addresses_nor_tokens(
    client, db_session, make_recipe, user, recipient
):
    """PRV-3, D-5: no email, no numeric user id, no planner data, no token."""
    share, token = _share_to(
        db_session, make_recipe("Ragu"), user, recipient_email=recipient.email
    )
    text = json.dumps(client.get(f"/shared-with-me/{share.id}").json())
    assert user.email not in text
    assert recipient.email not in text
    assert token not in text
    for forbidden in (
        "user_id", "recipe_id", "token", "score", "bulk_prep", "date_last",
    ):
        assert forbidden not in text


def test_another_persons_share_id_is_404_not_403(
    client, db_session, make_recipe, user
):
    """Sequential ids make 403 an enumeration oracle; it must be 404."""
    share, _ = _share_to(
        db_session, make_recipe("Ragu"), user, recipient_email="nobody@test.local"
    )
    resp = client.get(f"/shared-with-me/{share.id}")
    assert resp.status_code == 404


def test_an_unknown_id_is_the_identical_404(client, db_session, make_recipe, user):
    share, _ = _share_to(
        db_session, make_recipe("Ragu"), user, recipient_email="nobody@test.local"
    )
    theirs = client.get(f"/shared-with-me/{share.id}")
    missing = client.get("/shared-with-me/10000000")
    assert missing.status_code == theirs.status_code == 404
    assert missing.json() == theirs.json()


def test_a_revoked_share_cannot_be_viewed(
    client, db_session, make_recipe, user, recipient
):
    share, _ = _share_to(
        db_session, make_recipe("Ragu"), user, recipient_email=recipient.email
    )
    shares.revoke_share(db_session, share)
    assert client.get(f"/shared-with-me/{share.id}").status_code == 404


def test_an_expired_share_cannot_be_viewed(
    client, db_session, make_recipe, user, recipient
):
    share, _ = _share_to(
        db_session, make_recipe("Ragu"), user, recipient_email=recipient.email,
        expires_at=datetime.utcnow() - timedelta(seconds=1),
    )
    assert client.get(f"/shared-with-me/{share.id}").status_code == 404


def test_a_dismissed_share_cannot_be_viewed(
    client, db_session, make_recipe, user, recipient
):
    """SWM-3: dismissing removes the entry, and with it both actions."""
    share, _ = _share_to(
        db_session, make_recipe("Ragu"), user, recipient_email=recipient.email
    )
    client.post(f"/shared-with-me/{share.id}/dismiss")
    assert client.get(f"/shared-with-me/{share.id}").status_code == 404


def test_an_unverified_address_cannot_view(
    client, db_session, make_recipe, user, recipient
):
    """SWM-4."""
    share, _ = _share_to(
        db_session, make_recipe("Ragu"), user, recipient_email=recipient.email
    )
    recipient.email_verified = False
    db_session.flush()
    assert client.get(f"/shared-with-me/{share.id}").status_code == 404


# ---------------------------------------------------------------------------
# POST /shared-with-me/{share_id}/copy
# ---------------------------------------------------------------------------

def test_i_can_copy_an_entry_addressed_to_me(
    client, db_session, make_recipe, user, recipient
):
    """SWM-2, CP-1."""
    share, _ = _share_to(
        db_session, make_recipe("Ragu"), user, recipient_email=recipient.email
    )
    resp = client.post(f"/shared-with-me/{share.id}/copy")
    assert resp.status_code == 201
    body = resp.json()
    assert body["title"] == "Ragu"
    assert body["already_copied"] is False
    made = db_session.get(models.Recipe, body["id"])
    assert made.user_id == recipient.id


def test_the_copy_is_private_uncounted_and_unlaid_out(
    client, db_session, make_recipe, user, recipient
):
    """CP-4."""
    share, _ = _share_to(
        db_session, make_recipe("Ragu"), user, recipient_email=recipient.email
    )
    body = client.post(f"/shared-with-me/{share.id}/copy").json()
    made = db_session.get(models.Recipe, body["id"])
    assert made.visibility == "private"
    assert made.copy_count == 0
    assert made.page_layout is None


def test_the_copy_carries_no_planner_history(
    client, db_session, make_recipe, user, recipient
):
    """CP-7."""
    source = make_recipe("Ragu")
    source.score = 9.0
    source.date_last_consumed = datetime.utcnow().date()
    db_session.flush()
    share, _ = _share_to(db_session, source, user, recipient_email=recipient.email)
    body = client.post(f"/shared-with-me/{share.id}/copy").json()
    made = db_session.get(models.Recipe, body["id"])
    assert made.date_last_consumed is None
    assert made.date_last_rejected is None
    assert made.score != 9.0


def test_the_copy_snapshots_the_immediate_source(
    client, db_session, make_recipe, user, recipient
):
    """AT-1, AT-6."""
    share, _ = _share_to(
        db_session, make_recipe("Ragu"), user, recipient_email=recipient.email
    )
    body = client.post(f"/shared-with-me/{share.id}/copy").json()
    made = db_session.get(models.Recipe, body["id"])
    assert made.source_author_username == user.username
    assert made.source_recipe_title == "Ragu"
    assert made.copied_at is not None


def test_the_source_counts_a_copy_made_from_the_inbox(
    client, db_session, make_recipe, user, recipient
):
    """AT-7."""
    source = make_recipe("Ragu")
    share, _ = _share_to(db_session, source, user, recipient_email=recipient.email)
    client.post(f"/shared-with-me/{share.id}/copy")
    db_session.refresh(source)
    assert source.copy_count == 1


def test_copying_twice_warns_the_second_time(
    client, db_session, make_recipe, user, recipient
):
    """CP-11."""
    share, _ = _share_to(
        db_session, make_recipe("Ragu"), user, recipient_email=recipient.email
    )
    assert client.post(f"/shared-with-me/{share.id}/copy").json()[
        "already_copied"
    ] is False
    assert client.post(f"/shared-with-me/{share.id}/copy").json()[
        "already_copied"
    ] is True


def test_the_owner_cannot_copy_their_own_recipe_from_the_inbox(
    db_session, make_recipe, user, recipient
):
    """CP-10: 403, since the caller demonstrably already holds the row."""
    recipe = make_recipe("Ragu")
    share, _ = _share_to(db_session, recipe, user, recipient_user=user)
    user.email_verified = True
    db_session.flush()
    try:
        owner_client = client_as(db_session, user)
        assert owner_client.post(
            f"/shared-with-me/{share.id}/copy"
        ).status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_copying_another_persons_share_id_is_404_not_403(
    client, db_session, make_recipe, user
):
    share, _ = _share_to(
        db_session, make_recipe("Ragu"), user, recipient_email="nobody@test.local"
    )
    assert client.post(f"/shared-with-me/{share.id}/copy").status_code == 404


@pytest.mark.parametrize("kill", ["revoke", "expire", "dismiss", "unverify"])
def test_copying_fails_closed_for_every_dead_entry(
    client, db_session, make_recipe, user, recipient, kill
):
    share, _ = _share_to(
        db_session, make_recipe("Ragu"), user, recipient_email=recipient.email
    )
    if kill == "revoke":
        shares.revoke_share(db_session, share)
    elif kill == "expire":
        share.expires_at = datetime.utcnow() - timedelta(seconds=1)
        db_session.flush()
    elif kill == "dismiss":
        client.post(f"/shared-with-me/{share.id}/dismiss")
    else:
        recipient.email_verified = False
        db_session.flush()
    assert client.post(f"/shared-with-me/{share.id}/copy").status_code == 404


def test_the_copy_response_carries_no_token_and_no_source_ids(
    client, db_session, make_recipe, user, recipient
):
    """PRV-3, D-5."""
    share, token = _share_to(
        db_session, make_recipe("Ragu"), user, recipient_email=recipient.email
    )
    body = client.post(f"/shared-with-me/{share.id}/copy").json()
    assert set(body) == {"id", "title", "already_copied"}
    assert token not in json.dumps(body)


def test_the_copys_ingredients_live_in_my_own_namespace(
    client, db_session, make_recipe, user, recipient
):
    """CP-3."""
    source = make_recipe("Ragu")
    ingredient = crud.get_or_create_ingredient(db_session, None, "Beef", "g", user.id)
    source.ingredients.append(
        models.RecipeIngredient(ingredient=ingredient, quantity=200, unit="g")
    )
    db_session.flush()
    share, _ = _share_to(db_session, source, user, recipient_email=recipient.email)
    body = client.post(f"/shared-with-me/{share.id}/copy").json()
    made = db_session.get(models.Recipe, body["id"])
    assert [link.ingredient.name for link in made.ingredients] == ["Beef"]
    for link in made.ingredients:
        assert link.ingredient.user_id == recipient.id
        assert link.ingredient.id != ingredient.id
