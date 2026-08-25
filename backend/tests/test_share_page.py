"""The share page itself: ``GET /s/{token}`` (SH-22/23/24/26, RA-7, NF-2).

Companion file ``test_share_page_privacy.py`` carries the header and leakage
assertions; this one is about resolution, access control and rendering.
"""
from datetime import datetime, timedelta

import pytest
from sqlalchemy import event

import crud
import models
import shares
from tests.conftest import db_client


def _share_client(session, current_user=None):
    """A ``TestClient`` on ``session`` with the page's optional-auth override."""
    import public_pages
    from main import app

    client = db_client(session)
    app.dependency_overrides[public_pages.optional_current_user] = (
        lambda: current_user
    )
    return client


@pytest.fixture
def page_client(db_session):
    from main import app

    try:
        yield lambda user=None: _share_client(db_session, user)
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def shared_recipe(db_session, user):
    """A recipe with a tag and two ingredient lines, plus a live link share."""
    recipe = crud.create_recipe(
        db_session,
        title="Pasta al pomodoro",
        course="main",
        procedure="Boil the pasta. Add sauce.",
        user_id=user.id,
    )
    tag = models.Tag(name="quick", user_id=user.id)
    db_session.add(tag)
    db_session.flush()
    recipe.tags.append(tag)
    for name, qty in (("pasta", 200.0), ("tomato", 400.0)):
        ing = crud.create_ingredient(
            db_session,
            name=name,
            unit=models.UnitEnum.G,
            season_months=[],
            user_id=user.id,
        )
        db_session.add(
            models.RecipeIngredient(
                recipe_id=recipe.id, ingredient_id=ing.id, quantity=qty
            )
        )
    db_session.commit()
    share, token = shares.create_share(
        db_session, recipe=recipe, owner=user, mode="link"
    )
    db_session.commit()
    return share, token, recipe


# ---------------------------------------------------------------------------
# happy path
# ---------------------------------------------------------------------------
def test_link_share_renders_the_recipe_to_an_anonymous_visitor(
    page_client, shared_recipe
):
    _share, token, _recipe = shared_recipe
    response = page_client().get(f"/s/{token}")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "Pasta al pomodoro" in response.text
    assert "pasta" in response.text
    assert "Boil the pasta" in response.text


def test_page_contains_no_script_element_of_its_own(page_client, shared_recipe):
    """SP-2 is server-rendered; the page stays entirely JavaScript-free."""
    _share, token, _recipe = shared_recipe
    body = page_client().get(f"/s/{token}").text
    assert "<script" not in body.lower()


def test_servings_query_scales_the_ingredient_quantities(
    page_client, shared_recipe
):
    _share, token, _recipe = shared_recipe
    body = page_client().get(f"/s/{token}?servings=4").text
    # Stored quantities are per person, so four people want four times them.
    assert "800" in body  # 200 g of pasta
    assert "1600" in body  # 400 g of tomato


def test_page_renders_for_one_person_by_default(page_client, shared_recipe):
    """A recipe is stored per person, so an unscaled page renders for one."""
    _share, token, _recipe = shared_recipe
    body = page_client().get(f"/s/{token}").text
    assert 'value="1"' in body
    assert "200" in body
    assert "400" in body


def test_nonsense_servings_degrades_instead_of_erroring(
    page_client, shared_recipe
):
    _share, token, _recipe = shared_recipe
    for value in ("0", "-3", "abc", ""):
        response = page_client().get(f"/s/{token}?servings={value}")
        assert response.status_code == 200, value
        assert "200" in response.text, value


def test_copy_cta_links_at_the_frontend_shared_landing(
    page_client, shared_recipe
):
    _share, token, _recipe = shared_recipe
    body = page_client().get(f"/s/{token}").text
    assert f'href="http://localhost:3000/shared/{token}"' in body


# ---------------------------------------------------------------------------
# SH-22: one neutral 404 for every failure mode
# ---------------------------------------------------------------------------
def test_revoked_expired_and_unknown_tokens_return_identical_404s(
    db_session, user, page_client
):
    recipe = crud.create_recipe(
        db_session, title="R", course="main", user_id=user.id,
    )
    revoked, revoked_token = shares.create_share(
        db_session, recipe=recipe, owner=user, mode="link"
    )
    shares.revoke_share(db_session, revoked)
    _expired, expired_token = shares.create_share(
        db_session,
        recipe=recipe,
        owner=user,
        mode="link",
        expires_at=datetime.utcnow() - timedelta(days=1),
    )
    db_session.commit()

    client = page_client()
    responses = [
        client.get(f"/s/{revoked_token}"),
        client.get(f"/s/{expired_token}"),
        client.get("/s/" + "z" * 43),
    ]

    assert [r.status_code for r in responses] == [404, 404, 404]
    bodies = {r.content for r in responses}
    assert len(bodies) == 1, "the three 404 bodies must be byte-identical"


def test_unknown_token_404_leaks_no_recipe_or_reason(page_client):
    response = page_client().get("/s/" + "q" * 43)
    lowered = response.text.lower()
    for word in ("revoked", "expired", "unknown", "recipe", "share"):
        assert word not in lowered


# ---------------------------------------------------------------------------
# SH-23 / SH-24: person mode is not a bearer capability
# ---------------------------------------------------------------------------
@pytest.fixture
def person_share(db_session, user, other_user):
    recipe = crud.create_recipe(
        db_session, title="Just for you", course="main", user_id=user.id,
    )
    other_user.email_verified = True
    db_session.commit()
    share, token = shares.create_share(
        db_session,
        recipe=recipe,
        owner=user,
        mode="person",
        recipient_email=other_user.email,
    )
    db_session.commit()
    return share, token, recipe


def test_person_share_redirects_an_anonymous_visitor_to_login(
    page_client, person_share
):
    _share, token, _recipe = person_share
    response = page_client().get(f"/s/{token}", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"] == (
        f"http://localhost:3000/login?next=/s/{token}"
    )
    assert "Just for you" not in response.text


def test_person_share_refuses_the_wrong_signed_in_account(
    db_session, page_client, person_share, user
):
    _share, token, _recipe = person_share
    intruder = crud.create_user(
        db_session,
        email="Intruder@Example.COM",
        username="intruder",
        hashed_password="x",
        email_verified=True,
    )
    db_session.commit()

    response = page_client(intruder).get(f"/s/{token}")

    assert response.status_code == 403
    assert "Just for you" not in response.text
    # SH-24: the address is named, but masked.
    assert "other@test.local" not in response.text
    assert "o***r@test.local" in response.text


def test_person_share_refuses_a_matching_but_unverified_email(
    db_session, page_client, person_share, other_user
):
    """SH-4: only a *verified* address satisfies the recipient match."""
    _share, token, _recipe = person_share
    other_user.email_verified = False
    db_session.commit()

    response = page_client(other_user).get(f"/s/{token}")

    assert response.status_code == 403
    assert "Just for you" not in response.text


def test_person_share_renders_for_the_named_recipient(
    page_client, person_share, other_user
):
    _share, token, _recipe = person_share
    response = page_client(other_user).get(f"/s/{token}")

    assert response.status_code == 200
    assert "Just for you" in response.text


def test_person_share_matches_the_recipient_by_account_id(
    db_session, page_client, user, other_user
):
    recipe = crud.create_recipe(
        db_session, title="By id", course="main", user_id=user.id,
    )
    other_user.email_verified = True
    other_user.email = "renamed@test.local"
    db_session.commit()
    share, token = shares.create_share(
        db_session,
        recipe=recipe,
        owner=user,
        mode="person",
        recipient_user=other_user,
    )
    share.recipient_email = None
    db_session.commit()

    assert page_client(other_user).get(f"/s/{token}").status_code == 200


def test_link_share_ignores_a_named_recipient(
    db_session, page_client, user, other_user
):
    """SH-6: a link share with a recipient is still open to anyone."""
    recipe = crud.create_recipe(
        db_session, title="Open", course="main", user_id=user.id,
    )
    _share, token = shares.create_share(
        db_session,
        recipe=recipe,
        owner=user,
        mode="link",
        recipient_user=other_user,
    )
    db_session.commit()

    assert page_client().get(f"/s/{token}").status_code == 200


# ---------------------------------------------------------------------------
# SH-26: last_viewed_at, and nothing else
# ---------------------------------------------------------------------------
def test_successful_view_stamps_last_viewed_at(
    db_session, page_client, shared_recipe
):
    share, token, _recipe = shared_recipe
    assert share.last_viewed_at is None

    before = datetime.utcnow() - timedelta(seconds=5)
    page_client().get(f"/s/{token}")
    db_session.refresh(share)

    assert share.last_viewed_at is not None
    assert share.last_viewed_at >= before


def test_refused_view_stamps_nothing(db_session, page_client, person_share):
    share, token, _recipe = person_share
    page_client().get(f"/s/{token}", follow_redirects=False)
    db_session.refresh(share)
    assert share.last_viewed_at is None


# ---------------------------------------------------------------------------
# RA-7: OG tags
# ---------------------------------------------------------------------------
def test_og_image_is_absolutised_against_the_public_base_url(
    db_session, monkeypatch, page_client, shared_recipe
):
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://recipes.example")
    _share, token, recipe = shared_recipe
    recipe.image_url = "/media/pasta.jpg"
    db_session.commit()

    body = page_client().get(f"/s/{token}").text
    assert (
        '<meta property="og:image" '
        'content="https://recipes.example/media/pasta.jpg">' in body
    )
    assert 'name="twitter:card" content="summary_large_image"' in body


def test_absolute_image_url_is_not_prefixed(
    db_session, monkeypatch, page_client, shared_recipe
):
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://recipes.example")
    _share, token, recipe = shared_recipe
    recipe.image_url = "https://cdn.example/p.jpg"
    db_session.commit()

    assert 'content="https://cdn.example/p.jpg"' in (
        page_client().get(f"/s/{token}").text
    )


def test_a_hostile_image_url_cannot_hijack_the_og_image(
    db_session, monkeypatch, page_client, shared_recipe
):
    """RA-7: absolutisation must not be string concatenation."""
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://recipes.example")
    _share, token, recipe = shared_recipe
    recipe.image_url = "javascript:alert(1)"
    db_session.commit()

    body = page_client().get(f"/s/{token}").text
    assert "javascript:" not in body
    assert 'name="twitter:card" content="summary">' in body


def test_no_image_falls_back_to_a_summary_card(page_client, shared_recipe):
    _share, token, _recipe = shared_recipe
    body = page_client().get(f"/s/{token}").text
    assert 'name="twitter:card" content="summary">' in body
    assert "og:image" not in body


def test_page_has_no_json_ld_and_no_canonical(page_client, shared_recipe):
    """RA-9."""
    _share, token, _recipe = shared_recipe
    body = page_client().get(f"/s/{token}").text
    assert "application/ld+json" not in body
    assert 'rel="canonical"' not in body
    assert "schema.org" not in body


# ---------------------------------------------------------------------------
# D-9 / language
# ---------------------------------------------------------------------------
def test_accept_language_selects_the_english_copy(page_client, shared_recipe):
    _share, token, _recipe = shared_recipe
    body = page_client().get(
        f"/s/{token}", headers={"Accept-Language": "en-GB,en;q=0.9"}
    ).text
    assert 'lang="en"' in body


def test_default_language_is_italian(page_client, shared_recipe):
    _share, token, _recipe = shared_recipe
    assert 'lang="it"' in page_client().get(f"/s/{token}").text


# ---------------------------------------------------------------------------
# NF-2: one eager load, not a fan-out
# ---------------------------------------------------------------------------
def test_rendering_the_page_stays_within_a_small_query_budget(
    engine, page_client, shared_recipe
):
    _share, token, _recipe = shared_recipe
    statements = []

    def _count(conn, cursor, statement, params, context, executemany):
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", _count)
    try:
        response = page_client().get(f"/s/{token}")
    finally:
        event.remove(engine, "before_cursor_execute", _count)

    assert response.status_code == 200
    selects = [s for s in statements if s.lstrip().upper().startswith("SELECT")]
    assert len(selects) <= 6, "\n".join(selects)
