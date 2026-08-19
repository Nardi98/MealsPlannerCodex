"""Share creation, listing, and revocation (§5.1, §5.2).

Every route here is owner-scoped, so the tests spend at least as much effort on
what a *non*-owner sees (a 404 that admits nothing) as on the happy path. The
raw token is deliberately observable exactly once, in the creation response;
that too is asserted rather than assumed.
"""

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

import crud
import models
import shares
from conftest import client_as, reset_schema
from main import app


@pytest.fixture
def client(db_session, user):
    try:
        yield client_as(db_session, user)
    finally:
        app.dependency_overrides.clear()


def _create(client, recipe_id, **body):
    body.setdefault("mode", "link")
    return client.post(f"/recipes/{recipe_id}/shares", json=body)


# --- POST /recipes/{id}/shares --------------------------------------------

def test_creating_a_link_share_returns_a_usable_url(client, make_recipe, db_session):
    recipe = make_recipe("Ragu")
    resp = _create(client, recipe.id)
    assert resp.status_code == 201
    body = resp.json()
    token = body["url"].rsplit("/s/", 1)[1]
    assert shares.resolve(db_session, token).recipe_id == recipe.id


def test_creation_promotes_a_private_recipe_to_unlisted(client, make_recipe, db_session):
    """VIS-6."""
    recipe = make_recipe("Ragu")
    assert recipe.visibility == "private"
    _create(client, recipe.id)
    db_session.refresh(recipe)
    assert recipe.visibility == "unlisted"


def test_person_share_requires_a_recipient(client, make_recipe):
    """SH-5."""
    recipe = make_recipe("Ragu")
    resp = _create(client, recipe.id, mode="person")
    assert resp.status_code == 400


def test_link_share_recipient_is_optional(client, make_recipe):
    """SH-5."""
    assert _create(client, make_recipe("Ragu").id).status_code == 201


def test_an_unknown_mode_is_rejected(client, make_recipe):
    assert _create(client, make_recipe("Ragu").id, mode="broadcast").status_code == 422


def test_expiry_is_stored_when_supplied(client, make_recipe, db_session):
    """SH-9."""
    recipe = make_recipe("Ragu")
    when = datetime.utcnow() + timedelta(days=3)
    resp = _create(client, recipe.id, expires_at=when.isoformat())
    assert resp.status_code == 201
    share = db_session.get(models.RecipeShare, resp.json()["id"])
    assert share.expires_at is not None


def test_cannot_share_another_users_recipe(client, db_session, other_user):
    """Owner scoping: a foreign recipe is simply not there."""
    foreign = crud.create_recipe(
        db_session, title="Theirs", servings_default=2, user_id=other_user.id
    )
    assert _create(client, foreign.id).status_code == 404


def test_sharing_a_missing_recipe_is_the_same_404(client, db_session, other_user):
    foreign = crud.create_recipe(
        db_session, title="Theirs", servings_default=2, user_id=other_user.id
    )
    missing = _create(client, 10_000_000)
    theirs = _create(client, foreign.id)
    assert missing.status_code == theirs.status_code == 404
    assert missing.json() == theirs.json()


def test_creation_response_carries_no_token_hash(client, make_recipe):
    body = _create(client, make_recipe("Ragu").id).json()
    assert "token_hash" not in body


# --- GET /recipes/{id}/shares (SH-20) --------------------------------------

def test_owner_lists_their_shares_with_the_details_sh20_requires(
    client, make_recipe
):
    recipe = make_recipe("Ragu")
    _create(client, recipe.id, mode="person", recipient_email="Friend@Test.local")
    rows = client.get(f"/recipes/{recipe.id}/shares").json()
    assert len(rows) == 1
    row = rows[0]
    assert row["mode"] == "person"
    assert row["recipient_email"] == "friend@test.local"
    assert set(row) >= {
        "id", "mode", "recipient_email", "created_at",
        "last_viewed_at", "expires_at", "revoked_at", "active",
    }


def test_the_share_list_never_leaks_a_raw_token(client, make_recipe):
    recipe = make_recipe("Ragu")
    token = _create(client, recipe.id).json()["url"].rsplit("/s/", 1)[1]
    text = client.get(f"/recipes/{recipe.id}/shares").text
    assert token not in text
    assert shares.hash_token(token) not in text


def test_listing_another_users_recipe_shares_is_404(client, db_session, other_user):
    foreign = crud.create_recipe(
        db_session, title="Theirs", servings_default=2, user_id=other_user.id
    )
    shares.create_share(
        db_session, recipe=foreign, owner=other_user, mode="link"
    )
    assert client.get(f"/recipes/{foreign.id}/shares").status_code == 404


# --- DELETE /shares/{share_id} ---------------------------------------------

def test_revoking_a_share_kills_the_token(client, make_recipe, db_session):
    recipe = make_recipe("Ragu")
    created = _create(client, recipe.id).json()
    token = created["url"].rsplit("/s/", 1)[1]
    assert client.delete(f"/shares/{created['id']}").status_code == 204
    assert shares.resolve(db_session, token) is None


def test_revoking_the_last_share_demotes_the_recipe(client, make_recipe, db_session):
    """VIS-7."""
    recipe = make_recipe("Ragu")
    created = _create(client, recipe.id).json()
    client.delete(f"/shares/{created['id']}")
    db_session.refresh(recipe)
    assert recipe.visibility == "private"


def test_revoking_one_of_two_shares_keeps_the_recipe_unlisted(
    client, make_recipe, db_session
):
    recipe = make_recipe("Ragu")
    first = _create(client, recipe.id).json()
    _create(client, recipe.id)
    client.delete(f"/shares/{first['id']}")
    db_session.refresh(recipe)
    assert recipe.visibility == "unlisted"


def test_revoking_someone_elses_share_is_404(client, db_session, other_user):
    foreign = crud.create_recipe(
        db_session, title="Theirs", servings_default=2, user_id=other_user.id
    )
    share, _ = shares.create_share(
        db_session, recipe=foreign, owner=other_user, mode="link"
    )
    assert client.delete(f"/shares/{share.id}").status_code == 404


def test_revoking_a_nonexistent_share_is_the_same_404(client, db_session, other_user):
    foreign = crud.create_recipe(
        db_session, title="Theirs", servings_default=2, user_id=other_user.id
    )
    share, _ = shares.create_share(
        db_session, recipe=foreign, owner=other_user, mode="link"
    )
    missing = client.delete("/shares/10000000")
    theirs = client.delete(f"/shares/{share.id}")
    assert missing.status_code == theirs.status_code == 404
    assert missing.json() == theirs.json()


def test_revoking_twice_is_idempotent(client, make_recipe):
    created = _create(client, make_recipe("Ragu").id).json()
    assert client.delete(f"/shares/{created['id']}").status_code == 204
    assert client.delete(f"/shares/{created['id']}").status_code == 204


# --- SH-11 -----------------------------------------------------------------

def test_share_creation_is_rate_limited(engine, monkeypatch):
    monkeypatch.setattr(app.state.share_limiter, "enabled", True)
    import auth_users
    from database import SessionLocal

    session = SessionLocal()
    owner = crud.create_user(
        session, email="limited@test.local", username="limited",
        hashed_password="x",
    )
    recipe = crud.create_recipe(
        session, title="Ragu", servings_default=2, user_id=owner.id
    )
    recipe_id = recipe.id

    app.dependency_overrides[auth_users.get_current_user] = lambda: owner
    saw_429 = False
    try:
        with TestClient(app) as c:
            for _ in range(60):
                resp = c.post(f"/recipes/{recipe_id}/shares", json={"mode": "link"})
                if resp.status_code == 429:
                    saw_429 = True
                    break
    finally:
        app.dependency_overrides.clear()
        session.close()
        reset_schema(engine)
    assert saw_429
