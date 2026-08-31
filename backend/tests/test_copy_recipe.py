"""Copying a shared recipe, and the attribution that survives it (§7).

Two concerns dominate this file.

CP-3: the copy must live entirely in the copier's namespace. ``crud.get_or_create_ingredient``
resolves by *id* before name, so a copy path that forwards the source's
ingredient id can bind the copy to the source owner's rows. Several tests below
attack that from different angles -- a spy on the call, a same-name row the
copier already owns, and a sweep asserting every reachable row's ``user_id``.

The module under test is ``recipe_copy``, not ``copy``: a top-level
``backend/copy.py`` would shadow the standard library's ``copy`` for the whole
process (the backend root is ``sys.path[0]``), and SQLAlchemy imports it.

The person-mode gap: ``shares.resolve`` answers "is this token live", nothing
more. If the route stops there, a ``person`` share degrades into a link share.
The tests under "person mode" are the ones that hold that shut.
"""

import json
from datetime import date, datetime, timedelta

import pytest

import recipe_copy as copy_module
import crud
import models
import shares
from conftest import client_as
from main import app
from models import UnitEnum


@pytest.fixture
def copier(db_session):
    account = crud.create_user(
        db_session, email="copier@test.local", username="copier",
        hashed_password="x",
    )
    account.email_verified = True
    db_session.flush()
    return account


@pytest.fixture
def client(db_session, copier):
    try:
        yield client_as(db_session, copier)
    finally:
        app.dependency_overrides.clear()


def _add_ingredient(db_session, recipe, name, quantity, owner_id, unit=UnitEnum.G):
    ingredient = crud.get_or_create_ingredient(db_session, None, name, owner_id)
    recipe.ingredients.append(
        models.RecipeIngredient(ingredient=ingredient, quantity=quantity, unit=unit)
    )
    db_session.flush()
    return ingredient


def _add_tag(db_session, recipe, name, owner_id):
    tag = crud.get_or_create_tag(db_session, name, owner_id)
    recipe.tags.append(tag)
    db_session.flush()
    return tag


@pytest.fixture
def source(db_session, make_recipe, user):
    """A fully-populated recipe owned by the ``user`` fixture."""
    recipe = make_recipe("Ragu alla bolognese", procedure="Simmer.", image_url="/i/1.jpg")
    _add_ingredient(db_session, recipe, "Tomato", 400, user.id)
    _add_ingredient(db_session, recipe, "Beef", 300, user.id)
    _add_tag(db_session, recipe, "sunday", user.id)
    db_session.flush()
    return recipe


# ---------------------------------------------------------------------------
# copy.copy_recipe -- CP-2, CP-3, CP-4, CP-5, CP-7
# ---------------------------------------------------------------------------

def test_the_copy_is_owned_by_the_copier(db_session, source, copier):
    """CP-2."""
    made = copy_module.copy_recipe(db_session, source, copier)
    assert made.id != source.id
    assert made.user_id == copier.id
    assert made.title == source.title


def test_every_row_the_copy_touches_belongs_to_the_copier(db_session, source, copier):
    """CP-3: no cross-user reference anywhere in the copied graph."""
    made = copy_module.copy_recipe(db_session, source, copier)
    owners = {link.ingredient.user_id for link in made.ingredients}
    owners |= {tag.user_id for tag in made.tags}
    assert owners == {copier.id}


def test_the_copy_never_reuses_a_source_owned_ingredient_row(
    db_session, source, copier
):
    """CP-3, stated as identity rather than ownership."""
    made = copy_module.copy_recipe(db_session, source, copier)
    source_ids = {link.ingredient_id for link in source.ingredients}
    copy_ids = {link.ingredient_id for link in made.ingredients}
    assert source_ids and copy_ids
    assert source_ids.isdisjoint(copy_ids)


def test_ingredient_resolution_is_never_asked_to_use_an_id(
    db_session, source, copier, monkeypatch
):
    """CP-3 at its root cause: ``ingredient_id`` must always be ``None``.

    ``get_or_create_ingredient`` looks up by id *first*, so any non-``None`` id
    reaching it is the bug, whether or not this particular dataset happens to
    resolve safely.
    """
    seen = []
    real = crud.get_or_create_ingredient

    def spy(session, ingredient_id, name, user_id=None, **factors):
        seen.append((ingredient_id, user_id))
        return real(session, ingredient_id, name, user_id, **factors)

    monkeypatch.setattr(crud, "get_or_create_ingredient", spy)
    copy_module.copy_recipe(db_session, source, copier)
    assert seen
    assert all(ingredient_id is None for ingredient_id, _ in seen)
    assert all(user_id == copier.id for _, user_id in seen)


def test_a_colliding_name_binds_to_the_copiers_own_row(
    db_session, source, copier, user
):
    """CP-3: same name, two owners, two ids -- the copy takes the copier's.

    This is the shape an id collision actually takes in this schema: the two
    accounts hold rows with the same *name* and different ids, and resolving by
    anything but "name within my namespace" picks the wrong one.
    """
    mine = crud.get_or_create_ingredient(db_session, None, "Tomato", copier.id)
    my_tag = crud.get_or_create_tag(db_session, "sunday", copier.id)
    db_session.flush()
    theirs = {link.ingredient.name: link.ingredient for link in source.ingredients}
    assert theirs["Tomato"].id != mine.id

    made = copy_module.copy_recipe(db_session, source, copier)
    used = {link.ingredient.name: link.ingredient_id for link in made.ingredients}
    assert used["Tomato"] == mine.id
    assert [tag.id for tag in made.tags] == [my_tag.id]


def test_quantities_and_units_survive_the_copy(db_session, source, copier):
    made = copy_module.copy_recipe(db_session, source, copier)
    assert {
        link.ingredient.name: link.quantity for link in made.ingredients
    } == {"Tomato": 400.0, "Beef": 300.0}


def test_the_servings_basis_survives_the_copy(db_session, source, copier):
    """Quantities are copied verbatim, so the basis they were written for must
    come with them -- otherwise the copy silently means something else."""
    source.servings = 4
    db_session.flush()
    made = copy_module.copy_recipe(db_session, source, copier)
    assert made.servings == 4


def test_the_copy_starts_private_with_no_page_and_no_copies(
    db_session, source, copier
):
    """CP-4."""
    made = copy_module.copy_recipe(db_session, source, copier)
    assert made.visibility == "private"
    assert made.copy_count == 0
    assert made.page_layout is None


def test_planner_history_does_not_cross_accounts(db_session, source, copier):
    """CP-7."""
    source.score = 9.5
    source.date_last_consumed = date(2026, 1, 1)
    source.date_last_rejected = date(2026, 2, 1)
    db_session.flush()
    made = copy_module.copy_recipe(db_session, source, copier)
    assert made.score is None
    assert made.date_last_consumed is None
    assert made.date_last_rejected is None


def test_editing_the_copy_leaves_the_source_alone(db_session, source, copier):
    """CP-5."""
    made = copy_module.copy_recipe(db_session, source, copier)
    made.title = "My ragu"
    made.ingredients[0].quantity = 1.0
    db_session.flush()
    db_session.refresh(source)
    assert source.title == "Ragu alla bolognese"
    assert sorted(link.quantity for link in source.ingredients) == [300.0, 400.0]


def test_the_copy_path_does_not_use_the_self_committing_crud_helper(
    db_session, source, copier, monkeypatch
):
    """CP-8: ``crud.create_recipe`` commits internally, so it cannot be used."""
    def explode(*args, **kwargs):
        raise AssertionError("copy_recipe must not call crud.create_recipe")

    monkeypatch.setattr(crud, "create_recipe", explode)
    assert copy_module.copy_recipe(db_session, source, copier) is not None


def test_the_copy_commits_exactly_once(db_session, source, copier, monkeypatch):
    """CP-8: one commit, at the end, or a partial copy becomes observable."""
    commits = []
    real = db_session.commit
    monkeypatch.setattr(
        db_session, "commit", lambda: (commits.append(1), real())[1]
    )
    copy_module.copy_recipe(db_session, source, copier)
    assert len(commits) == 1


def test_a_failure_mid_copy_commits_nothing(db_session, source, copier, monkeypatch):
    """CP-8: nothing lands if any part of the copy fails."""
    commits = []
    monkeypatch.setattr(db_session, "commit", lambda: commits.append(1))

    def explode(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(crud, "get_or_create_tag", explode)
    with pytest.raises(RuntimeError):
        copy_module.copy_recipe(db_session, source, copier)
    assert commits == []


def test_copying_your_own_recipe_is_refused_in_the_domain_layer(
    db_session, source, user
):
    """CP-10."""
    with pytest.raises(PermissionError):
        copy_module.copy_recipe(db_session, source, user)


# --- CP-6 favourite sides --------------------------------------------------

def test_favourite_sides_are_copied_and_relinked(db_session, source, copier, user):
    side = crud.create_recipe(
        db_session, title="Insalata", course="side", user_id=user.id,
    )
    source.favorite_sides.append(side)
    db_session.flush()

    made = copy_module.copy_recipe(db_session, source, copier)
    assert [s.title for s in made.favorite_sides] == ["Insalata"]
    copied_side = made.favorite_sides[0]
    assert copied_side.id != side.id
    assert copied_side.user_id == copier.id


def test_a_side_owned_by_a_third_party_is_dropped_silently(
    db_session, source, copier, other_user
):
    """CP-6: unreachable through this share, so it does not come along."""
    foreign_side = crud.create_recipe(
        db_session, title="Theirs", course="side", user_id=other_user.id,
    )
    source.favorite_sides.append(foreign_side)
    db_session.flush()
    made = copy_module.copy_recipe(db_session, source, copier)
    assert made.favorite_sides == []


# --- attribution -----------------------------------------------------------

def test_the_copy_snapshots_its_source(db_session, source, copier, user):
    """AT-1."""
    made = copy_module.copy_recipe(db_session, source, copier)
    assert made.source_recipe_id == source.id
    assert made.source_user_id == user.id
    assert made.source_author_username == user.username
    assert made.source_recipe_title == "Ragu alla bolognese"
    assert made.copied_at is not None


def test_copying_a_copy_credits_only_the_immediate_source(
    db_session, source, copier, other_user, user
):
    """AT-6."""
    first = copy_module.copy_recipe(db_session, source, copier)
    second = copy_module.copy_recipe(db_session, first, other_user)
    assert second.source_author_username == copier.username
    assert second.source_recipe_id == first.id
    assert second.source_user_id == copier.id


def test_the_source_counts_the_copy(db_session, source, copier, other_user):
    """AT-7."""
    assert source.copy_count == 0
    copy_module.copy_recipe(db_session, source, copier)
    copy_module.copy_recipe(db_session, source, other_user)
    db_session.refresh(source)
    assert source.copy_count == 2


def test_attribution_survives_deletion_of_the_source(db_session, source, copier):
    """AT-2."""
    made = copy_module.copy_recipe(db_session, source, copier)
    crud.delete_recipe(db_session, source.id, source.user_id)
    db_session.refresh(made)
    assert made.source_recipe_id is None
    assert made.source_author_username == "owner"
    assert made.source_recipe_title == "Ragu alla bolognese"


# ---------------------------------------------------------------------------
# POST /s/{token}/copy
# ---------------------------------------------------------------------------

def _link_share(db_session, recipe, owner, **kwargs):
    share, token = shares.create_share(
        db_session, recipe=recipe, owner=owner, mode=kwargs.pop("mode", "link"),
        **kwargs,
    )
    db_session.flush()
    return share, token


def test_copying_through_a_valid_link(client, db_session, source, user, copier):
    """CP-1."""
    _, token = _link_share(db_session, source, user)
    resp = client.post(f"/s/{token}/copy")
    assert resp.status_code == 201
    body = resp.json()
    assert body["already_copied"] is False
    made = db_session.get(models.Recipe, body["id"])
    assert made.user_id == copier.id


def test_a_revoked_expired_or_unknown_token_is_one_identical_404(
    client, db_session, source, user
):
    """SH-22."""
    revoked_share, revoked = _link_share(db_session, source, user)
    shares.revoke_share(db_session, revoked_share)
    _, expired = _link_share(
        db_session, source, user,
        expires_at=datetime.utcnow() - timedelta(seconds=1),
    )
    responses = [
        client.post(f"/s/{revoked}/copy"),
        client.post(f"/s/{expired}/copy"),
        client.post("/s/definitely-not-a-token/copy"),
    ]
    assert {r.status_code for r in responses} == {404}
    assert len({r.text for r in responses}) == 1


def test_the_owner_cannot_copy_their_own_recipe(db_session, source, user):
    """CP-10."""
    _, token = _link_share(db_session, source, user)
    try:
        owner_client = client_as(db_session, user)
        assert owner_client.post(f"/s/{token}/copy").status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_copying_twice_is_allowed_and_says_so(client, db_session, source, user, copier):
    """CP-11."""
    _, token = _link_share(db_session, source, user)
    first = client.post(f"/s/{token}/copy").json()
    second = client.post(f"/s/{token}/copy").json()
    assert first["already_copied"] is False
    assert second["already_copied"] is True
    assert first["id"] != second["id"]
    mine = db_session.query(models.Recipe).filter_by(user_id=copier.id).count()
    assert mine == 2


def test_the_copy_response_leaks_nothing_about_the_source(
    client, db_session, source, user
):
    """PRV-3: not the source's ids, not its owner."""
    _, token = _link_share(db_session, source, user)
    body = client.post(f"/s/{token}/copy").json()
    text = json.dumps(body)
    assert user.email not in text
    assert "source" not in text
    assert "user_id" not in text


# --- person mode: the gap shares.resolve deliberately leaves open ----------

def test_a_person_share_lets_the_named_verified_recipient_copy(
    client, db_session, source, user, copier
):
    """SH-4."""
    _, token = _link_share(
        db_session, source, user, mode="person", recipient_email=copier.email
    )
    assert client.post(f"/s/{token}/copy").status_code == 201


def test_a_person_share_naming_the_account_lets_that_account_copy(
    client, db_session, source, user, copier
):
    _, token = _link_share(
        db_session, source, user, mode="person", recipient_user=copier
    )
    assert client.post(f"/s/{token}/copy").status_code == 201


def test_a_signed_in_non_recipient_cannot_copy_a_person_share(
    client, db_session, source, user
):
    """The gap: without this check a person share is just a link share."""
    _, token = _link_share(
        db_session, source, user, mode="person",
        recipient_email="somebody-else@test.local",
    )
    assert client.post(f"/s/{token}/copy").status_code == 403


def test_an_unverified_account_matching_the_named_email_cannot_copy(
    client, db_session, source, user, copier
):
    """SH-4/SWM-4: an unproven address must never satisfy the match."""
    copier.email_verified = False
    db_session.flush()
    _, token = _link_share(
        db_session, source, user, mode="person", recipient_email=copier.email
    )
    assert client.post(f"/s/{token}/copy").status_code == 403


def test_the_named_email_is_matched_case_insensitively(
    client, db_session, source, user, copier
):
    _, token = _link_share(
        db_session, source, user, mode="person",
        recipient_email="  COPIER@Test.Local ",
    )
    assert client.post(f"/s/{token}/copy").status_code == 201


def test_a_link_share_naming_somebody_else_is_still_open(
    client, db_session, source, user
):
    """SH-6: naming a recipient in link mode restricts nothing."""
    _, token = _link_share(
        db_session, source, user, recipient_email="somebody-else@test.local"
    )
    assert client.post(f"/s/{token}/copy").status_code == 201


# --- CP-9 ------------------------------------------------------------------

def test_copying_is_rate_limited(engine, monkeypatch):
    """CP-9. Copying is cheap for the caller and expensive for the server."""
    import auth_users
    from fastapi.testclient import TestClient
    from conftest import reset_schema
    from database import SessionLocal

    monkeypatch.setattr(app.state.share_limiter, "enabled", True)
    session = SessionLocal()
    owner = crud.create_user(
        session, email="sharer2@test.local", username="sharer2", hashed_password="x",
    )
    thief = crud.create_user(
        session, email="thief@test.local", username="thief", hashed_password="x",
    )
    thief.email_verified = True
    recipe = crud.create_recipe(
        session, title="Ragu", user_id=owner.id
    )
    _, token = shares.create_share(
        session, recipe=recipe, owner=owner, mode="link"
    )
    session.commit()

    app.dependency_overrides[auth_users.get_current_user] = lambda: thief
    saw_429 = False
    try:
        with TestClient(app) as c:
            for _ in range(60):
                if c.post(f"/s/{token}/copy").status_code == 429:
                    saw_429 = True
                    break
    finally:
        app.dependency_overrides.clear()
        session.close()
        reset_schema(engine)
    assert saw_429


# --- AT-4 ------------------------------------------------------------------

def test_the_copier_cannot_edit_the_attribution_away(
    client, db_session, source, user, copier
):
    """AT-4: ``RecipeIn`` has no such field, so Pydantic drops it. Locked in."""
    made = copy_module.copy_recipe(db_session, source, copier)
    resp = client.put(
        f"/recipes/{made.id}",
        json={
            "title": "Mine now",
            "course": "main",
            "source_author_username": "copier",
            "source_recipe_title": "Mine now",
            "source_recipe_id": None,
        },
    )
    assert resp.status_code == 200
    db_session.refresh(made)
    assert made.source_author_username == user.username
    assert made.source_recipe_title == "Ragu alla bolognese"
    assert made.source_recipe_id == source.id
