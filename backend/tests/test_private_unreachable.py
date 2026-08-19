"""VIS-10: a ``private`` recipe is unreachable without credentials.

This is the requirement the whole sharing feature is measured against. Every
other test in the suite asks "does this route do the right thing"; this one asks
the complementary question -- "is there *any* way in" -- and it has to be
written as a sweep, because the failure mode it guards against is not a route
behaving wrongly but a route that nobody thought to check.

So the central test walks ``app.routes`` and fires an unauthenticated request at
every one of them, substituting the private recipe's real id (and its owner's
real handle) into every path parameter that plausibly names one. Nothing may
answer with the recipe's title. A route added next month is swept the day it is
added, and if it leaks it fails here without anyone having to remember to come
back and add a case.

The second half covers the specific surfaces the spec names: ``/s/{token}`` for
a token that is well-formed but was never minted (SH-22 -- guessing must be
indistinguishable from a revoked link), and ``PUT``ting ``visibility: public``,
which VIS-5 says is rejected with 400 because the capability does not exist yet.
"""
from __future__ import annotations

import secrets

import pytest

import crud
from tests.conftest import client_as, get_route_paths

#: The string that must never come back. Distinctive enough that a substring
#: match cannot collide with template chrome or an error message.
SECRET_TITLE = "Nonna's Zabaione Segretissimo"

#: A private recipe also holds private *contents*. Asserting only on the title
#: would let a route that returns the procedure but not the name pass.
SECRET_PROCEDURE = "Whisk the yolks with the marsala at exactly 63 degrees."

#: Values substituted into path parameters during the sweep. The recipe id and
#: the owner's handle are filled in per-test; everything else is a placeholder
#: chosen so a route that ignores it still returns *something* to inspect.
_FILLER = "1"


@pytest.fixture
def private_recipe(db_session, user):
    """A recipe left at its default ``private`` visibility, with no shares."""
    recipe = crud.create_recipe(
        db_session,
        title=SECRET_TITLE,
        course="main",
        servings_default=2,
        procedure=SECRET_PROCEDURE,
        user_id=user.id,
    )
    db_session.commit()
    assert recipe.visibility == "private", (
        "the fixture must start private or this whole file proves nothing"
    )
    return recipe


def _substitute(path: str, recipe_id: int, handle: str) -> str:
    """Fill a route's path parameters with values that name the private recipe.

    Every ``{...}`` placeholder gets a value; the ones whose names suggest a
    recipe or a user get the *real* ones, so the sweep is actually pointing at
    the row it is trying to extract rather than at a guaranteed 404.
    """
    filled = path
    while "{" in filled:
        start = filled.index("{")
        end = filled.index("}", start)
        name = filled[start + 1:end].split(":", 1)[0].lower()
        if "recipe" in name or name in {"id", "item_id"}:
            value = str(recipe_id)
        elif "user" in name or name == "u":
            value = handle
        else:
            value = _FILLER
        filled = filled[:start] + value + filled[end + 1:]
    return filled


def test_no_unauthenticated_get_route_returns_a_private_recipe(
    anon, private_recipe, user
):
    """The sweep. Nothing, anywhere, hands a private recipe to a stranger."""
    from main import app

    leaks = []
    for path in get_route_paths(app):
        target = _substitute(path, private_recipe.id, user.username)
        try:
            response = anon.get(target, follow_redirects=False)
        except Exception:
            # A route that raises on a placeholder it cannot parse has not
            # returned the recipe, which is all this test asserts.
            continue
        body = response.text or ""
        if SECRET_TITLE in body or SECRET_PROCEDURE in body:
            leaks.append((target, response.status_code))

    assert leaks == [], (
        "a private recipe was readable without authentication (VIS-10): "
        f"{leaks}"
    )


@pytest.mark.parametrize(
    "path",
    [
        "/recipes/{id}",
        "/recipes",
        "/shared-with-me",
        "/shared-with-me/{id}",
        "/recipes/{id}/shares",
    ],
)
def test_named_read_routes_refuse_anonymous_callers(anon, private_recipe, path):
    """The routes that *would* serve it if authenticated answer 401/403/404.

    Spelled out alongside the sweep because the sweep only proves the body did
    not contain the title -- a route answering 200 with an empty list would
    pass it. These pin the status as well.
    """
    target = path.replace("{id}", str(private_recipe.id))
    response = anon.get(target, follow_redirects=False)

    assert response.status_code in (401, 403, 404), (
        f"{target} answered {response.status_code} to an anonymous caller"
    )


def test_a_plausible_but_unminted_share_token_is_a_neutral_404(
    anon, private_recipe
):
    """SH-22: guessing a token looks exactly like following a revoked one.

    The token is generated the same way a real one is, so it is well-formed and
    of the right length -- the response must not distinguish "wrong shape" from
    "no such share".
    """
    plausible = secrets.token_urlsafe(32)

    response = anon.get(f"/s/{plausible}", follow_redirects=False)

    assert response.status_code == 404
    assert SECRET_TITLE not in response.text
    assert response.text == "Not Found"


def test_an_unminted_token_is_byte_identical_to_a_revoked_one(
    anon, db_session, private_recipe, user
):
    """The neutral-404 contract, asserted as an equality rather than a shape.

    Two responses that merely *look* similar are not what SH-22 asks for. If
    the bodies or the statuses ever diverge, holding a revoked link becomes
    distinguishable from holding a wrong one -- which tells an attacker that
    the recipe exists.
    """
    import shares

    share, token = shares.create_share(
        db_session, recipe=private_recipe, owner=user, mode="link"
    )
    shares.revoke_share(db_session, share)
    db_session.commit()

    revoked = anon.get(f"/s/{token}", follow_redirects=False)
    never_existed = anon.get(f"/s/{secrets.token_urlsafe(32)}", follow_redirects=False)

    assert revoked.status_code == never_existed.status_code == 404
    assert revoked.text == never_existed.text
    assert revoked.headers.get("content-type") == never_existed.headers.get(
        "content-type"
    )


def test_the_share_page_sets_no_cookie_for_an_anonymous_visitor(anon):
    """PRV-6, asserted on the 404 path where it is easiest to forget.

    A ``Set-Cookie`` on the neutral 404 would make the "this discloses nothing"
    claim false in a way no body comparison catches: the cookie is state, and
    state on a miss is a signal.
    """
    response = anon.get(f"/s/{secrets.token_urlsafe(32)}", follow_redirects=False)

    assert "set-cookie" not in {k.lower() for k in response.headers}


# ---------------------------------------------------------------------------
# VIS-5: ``public`` is refused
# ---------------------------------------------------------------------------
def test_setting_a_recipe_to_public_is_rejected_with_400(
    db_session, private_recipe, user
):
    """VIS-5/VIS-10. 400 and the stated message, not Pydantic's generic 422.

    The status matters as much as the refusal: 422 reads as "you sent a
    malformed field", and the client's correct reaction to that is to fix the
    field. 400 with this message reads as "that capability does not exist",
    whose correct reaction is to stop asking.
    """
    from main import app
    import schemas

    client = client_as(db_session, user)
    try:
        response = client.put(
            f"/recipes/{private_recipe.id}",
            json={
                "title": SECRET_TITLE,
                "course": "main",
                "servings_default": 2,
                "visibility": "public",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400
    assert schemas.PUBLIC_VISIBILITY_MESSAGE in response.text
    db_session.refresh(private_recipe)
    assert private_recipe.visibility == "private"


def test_creating_a_recipe_as_public_is_rejected_with_400(db_session, user):
    """The create path too -- VIS-5 is about the value, not about one verb."""
    from main import app
    import schemas

    client = client_as(db_session, user)
    try:
        response = client.post(
            "/recipes",
            json={
                "title": "Attempted public recipe",
                "course": "main",
                "servings_default": 2,
                "visibility": "public",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400
    assert schemas.PUBLIC_VISIBILITY_MESSAGE in response.text


def test_sharing_never_promotes_a_recipe_past_unlisted(
    db_session, private_recipe, user
):
    """VIS-6: the only promotion sharing performs is private -> unlisted.

    ``public`` is inert in this release, so no code path may reach it. Asserted
    here rather than only in the domain tests because VIS-10's claim ("private
    is unreachable, public is rejected") is false if a share can quietly set
    it.
    """
    import shares

    shares.create_share(db_session, recipe=private_recipe, owner=user, mode="link")
    db_session.commit()

    assert private_recipe.visibility == "unlisted"


def test_the_schema_validator_refuses_public_without_a_request():
    """The refusal at its source, one layer below the two 400 tests above.

    Those go through the route and so also prove the 400 *mapping*; this proves
    the rule itself, which is what a future route reusing the schema inherits.
    ``public`` remains a legal *column* value (Part 2 will use it), so the
    guarantee lives in the input schema, not in the model.
    """
    import pydantic

    import schemas

    with pytest.raises(pydantic.ValidationError) as caught:
        schemas.RecipeIn(
            title="Attempted public recipe",
            course="main",
            servings_default=2,
            visibility="public",
        )

    assert schemas.PUBLIC_VISIBILITY_MESSAGE in str(caught.value)
