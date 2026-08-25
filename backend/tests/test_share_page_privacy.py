"""Headers and leakage assertions for ``GET /s/{token}`` (PRV-3/6, RA-8, SH-28).

Split from ``test_share_page.py`` because these are the assertions that must
never be relaxed to make a feature fit: they are the page's contract with a
visitor who never agreed to anything.
"""
import re

import pytest

import crud
import models
import shares
from tests.conftest import db_client


@pytest.fixture
def page_client(db_session):
    from main import app
    import public_pages

    def _make(current_user=None):
        client = db_client(db_session)
        app.dependency_overrides[public_pages.optional_current_user] = (
            lambda: current_user
        )
        return client

    try:
        yield _make
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def rich_recipe(db_session, user):
    """A recipe carrying every field PRV-3 forbids the page to emit."""
    recipe = crud.create_recipe(
        db_session,
        title="Ragu",
        course="main",
        procedure="Simmer.",
        bulk_prep=True,
        score=7.25,
        user_id=user.id,
    )
    import datetime as _dt

    recipe.date_last_consumed = _dt.date(2026, 1, 2)
    recipe.date_last_rejected = _dt.date(2026, 1, 3)
    ing = crud.create_ingredient(
        db_session,
        name="beef",
        unit=models.UnitEnum.G,
        season_months=[],
        user_id=user.id,
    )
    db_session.add(
        models.RecipeIngredient(
            recipe_id=recipe.id, ingredient_id=ing.id, quantity=500.0
        )
    )
    db_session.commit()
    _share, token = shares.create_share(
        db_session, recipe=recipe, owner=user, mode="link"
    )
    db_session.commit()
    return recipe, token


# ---------------------------------------------------------------------------
# headers
# ---------------------------------------------------------------------------
def test_response_carries_the_full_header_set(page_client, rich_recipe):
    _recipe, token = rich_recipe
    headers = page_client().get(f"/s/{token}").headers

    assert headers["cache-control"] == "private, no-store"
    assert headers["referrer-policy"] == "no-referrer"  # SH-28
    assert headers["x-robots-tag"] == "noindex, nofollow"  # RA-8
    assert headers["vary"] == "Accept-Language"  # D-9
    assert headers["content-security-policy"] == (
        "default-src 'self'; script-src 'none'"
    )


def test_meta_robots_accompanies_the_header(page_client, rich_recipe):
    _recipe, token = rich_recipe
    assert 'name="robots"' in page_client().get(f"/s/{token}").text


def test_no_set_cookie_for_an_anonymous_visitor(page_client, rich_recipe):
    """PRV-6."""
    _recipe, token = rich_recipe
    response = page_client().get(f"/s/{token}")
    assert "set-cookie" not in {k.lower() for k in response.headers}


def test_no_set_cookie_for_a_signed_in_visitor(
    db_session, page_client, rich_recipe, other_user
):
    _recipe, token = rich_recipe
    response = page_client(other_user).get(f"/s/{token}")
    assert "set-cookie" not in {k.lower() for k in response.headers}


def test_404_also_sets_no_cookie_and_stays_noindex(page_client):
    response = page_client().get("/s/" + "n" * 43)
    assert response.status_code == 404
    assert "set-cookie" not in {k.lower() for k in response.headers}


# ---------------------------------------------------------------------------
# PRV-3: the rendered bytes, comments included
# ---------------------------------------------------------------------------
FORBIDDEN_SUBSTRINGS = (
    "bulk_prep",
    "date_last_consumed",
    "date_last_rejected",
    "score",
    "user_id",
    "meal_plan",
    "@test.local",
)


def test_rendered_page_contains_no_private_field(page_client, rich_recipe):
    _recipe, token = rich_recipe
    body = page_client().get(f"/s/{token}").text
    for needle in FORBIDDEN_SUBSTRINGS:
        assert needle not in body, needle


def test_html_comments_contain_no_recipe_or_account_data(
    page_client, rich_recipe
):
    recipe, token = rich_recipe
    body = page_client().get(f"/s/{token}").text
    comments = " ".join(re.findall(r"<!--(.*?)-->", body, re.S))
    for needle in FORBIDDEN_SUBSTRINGS + (recipe.title, "Simmer", "beef"):
        assert needle not in comments, needle


def test_page_does_not_leak_another_share_token(
    db_session, page_client, rich_recipe, user
):
    """The page's own token is legitimate (SP-3 CTA); no other one is."""
    recipe, token = rich_recipe
    _other_share, other_token = shares.create_share(
        db_session, recipe=recipe, owner=user, mode="link"
    )
    db_session.commit()

    body = page_client().get(f"/s/{token}").text
    assert other_token not in body


def test_page_shows_no_numeric_database_id(page_client, rich_recipe):
    recipe, token = rich_recipe
    body = page_client().get(f"/s/{token}").text
    assert f'"{recipe.id}"' not in body
    assert f"/recipes/{recipe.id}" not in body


def test_person_share_403_masks_the_recipient_address(
    db_session, page_client, user
):
    recipe = crud.create_recipe(
        db_session, title="Secret", course="main", user_id=user.id,
    )
    _share, token = shares.create_share(
        db_session,
        recipe=recipe,
        owner=user,
        mode="person",
        recipient_email="recipient@example.com",
    )
    intruder = crud.create_user(
        db_session,
        email="nope@example.com",
        username="nope",
        hashed_password="x",
        email_verified=True,
    )
    db_session.commit()

    body = page_client(intruder).get(f"/s/{token}").text
    assert "recipient@example.com" not in body
    assert "r*******t@example.com" in body


@pytest.mark.parametrize(
    "address,masked",
    [
        ("a@b.com", "*@b.com"),
        ("ab@b.com", "**@b.com"),
        ("abc@b.com", "a*c@b.com"),
        ("alessandro@example.org", "a********o@example.org"),
        ("nodomain", "********"),
    ],
)
def test_mask_email_never_reveals_the_local_part(address, masked):
    import public_pages

    assert public_pages.mask_email(address) == masked
