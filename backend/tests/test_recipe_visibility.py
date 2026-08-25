"""VIS-1/VIS-2/VIS-5/VIS-8 and the FC-3/FC-4/AT-1 columns on ``Recipe``."""

import pytest
from sqlalchemy import text

import crud
import schemas
from models import VISIBILITY_VALUES, Recipe


def test_visibility_admits_exactly_three_values():
    """VIS-1: all three defined now, so Part 2 enables rather than migrates."""
    assert VISIBILITY_VALUES == ("private", "unlisted", "public")


def test_a_new_recipe_is_private(db_session, user):
    """VIS-2 at the ORM level."""
    recipe = crud.create_recipe(
        db_session, title="Pesto", user_id=user.id
    )
    assert recipe.visibility == "private"


def test_visibility_defaults_to_private_at_the_database_level(db_session, user):
    """VIS-2: a row inserted around the ORM is still private."""
    db_session.execute(
        text(
            "INSERT INTO recipes (title, course, user_id) "
            "VALUES ('Raw insert', 'main', :uid)"
        ),
        {"uid": user.id},
    )
    stored = db_session.execute(
        text("SELECT visibility FROM recipes WHERE title = 'Raw insert'")
    ).scalar_one()
    assert stored == "private"


def test_recipe_carries_the_forward_compatible_page_columns(db_session, user):
    """FC-3 / FC-4: both nullable, both NULL for every recipe in this release."""
    recipe = crud.create_recipe(
        db_session, title="Focaccia", user_id=user.id
    )
    assert recipe.page_layout is None
    assert recipe.page_theme is None


def test_recipe_starts_with_no_copies_and_no_lineage(db_session, user):
    """AT-1 columns exist and are empty until a copy is made."""
    recipe = crud.create_recipe(
        db_session, title="Ragu", user_id=user.id
    )
    assert recipe.copy_count == 0
    assert recipe.source_recipe_id is None
    assert recipe.source_user_id is None
    assert recipe.source_author_username is None
    assert recipe.source_recipe_title is None
    assert recipe.copied_at is None


def test_deleting_the_source_preserves_the_attribution_snapshot(db_session, user):
    """AT-2 / AT-6: ``ON DELETE SET NULL`` keeps the credit text intact."""
    source = crud.create_recipe(
        db_session, title="Original", user_id=user.id
    )
    copy = crud.create_recipe(
        db_session,
        title="My Original",
        user_id=user.id,
        source_recipe_id=source.id,
        source_user_id=user.id,
        source_author_username="chef_anna",
        source_recipe_title="Original",
    )
    db_session.delete(source)
    db_session.flush()
    db_session.refresh(copy)

    assert copy.source_recipe_id is None
    assert copy.source_author_username == "chef_anna"
    assert copy.source_recipe_title == "Original"


def test_recipe_in_defaults_to_private():
    """VIS-2 at the schema layer."""
    assert schemas.RecipeIn(title="X").visibility == "private"


def test_recipe_in_accepts_unlisted():
    payload = schemas.RecipeIn(
        title="X", visibility="unlisted"
    )
    assert payload.visibility == "unlisted"


def test_recipe_in_rejects_public():
    """VIS-5: the capability is defined but unreachable in this release."""
    with pytest.raises(ValueError) as exc:
        schemas.RecipeIn(title="X", visibility="public")
    assert "Public recipes are not available yet" in str(exc.value)


def test_recipe_in_rejects_an_unknown_visibility():
    with pytest.raises(ValueError):
        schemas.RecipeIn(title="X", visibility="whatever")


def test_recipe_out_exposes_visibility_and_attribution(db_session, user):
    """AT-3: attribution has to reach the authenticated view."""
    recipe = crud.create_recipe(
        db_session,
        title="Copy",
        user_id=user.id,
        source_author_username="chef_anna",
        source_recipe_title="Original",
    )
    out = schemas.RecipeOut.model_validate(recipe)
    assert out.visibility == "private"
    assert out.copy_count == 0
    assert out.source_author_username == "chef_anna"
    assert out.source_recipe_title == "Original"
    assert out.copied_at is None


def test_only_the_owner_can_change_visibility(api_client):
    """VIS-8: the recipe routes are owner-scoped, so a stranger gets a 404."""
    created = api_client.post(
        "/recipes", json={"title": "Mine"}
    )
    assert created.status_code == 201, created.text
    recipe_id = created.json()["id"]

    import auth_users
    from main import app
    from database import SessionLocal

    session = SessionLocal()
    try:
        stranger = crud.create_user(
            session, email="stranger@test.local", hashed_password="x"
        )
        session.expunge(stranger)
    finally:
        session.close()

    app.dependency_overrides[auth_users.get_current_user] = lambda: stranger
    try:
        blocked = api_client.put(
            f"/recipes/{recipe_id}",
            json={"title": "Mine", "visibility": "unlisted"},
        )
        assert blocked.status_code == 404
    finally:
        app.dependency_overrides[auth_users.get_current_user] = (
            lambda: api_client.current_user
        )


def test_setting_public_through_the_api_is_rejected(api_client):
    """VIS-5 end to end: HTTP 400 with the stated message."""
    created = api_client.post(
        "/recipes", json={"title": "Mine"}
    )
    recipe_id = created.json()["id"]

    response = api_client.put(
        f"/recipes/{recipe_id}",
        json={"title": "Mine", "visibility": "public"},
    )
    assert response.status_code == 400
    assert "Public recipes are not available yet" in response.text


def test_visibility_round_trips_through_the_api(api_client):
    created = api_client.post(
        "/recipes",
        json={"title": "Shared", "visibility": "unlisted"},
    )
    assert created.status_code == 201, created.text
    assert created.json()["visibility"] == "unlisted"
