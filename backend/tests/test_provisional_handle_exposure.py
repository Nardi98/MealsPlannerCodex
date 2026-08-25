"""UN-11, enforced by the server rather than only by the SPA's gate.

The gate in ``App.jsx`` renders nothing but the handle-selection page while
``username_confirmed`` is false. That is the right *product* behaviour and the
wrong place to stop, because it is a rendering decision in the client. The
account already holds a valid access token; anything it can be persuaded not to
draw, ``curl`` can still ask for. A client-side gate is a UX affordance, and
treating one as a security boundary is how this class of bug always happens.

What is actually at stake
-------------------------
An unconfirmed handle is *system-derived*: ``crud._derive_username`` builds it
from the email local part, so ``giulia.bianchi@clinic.example`` becomes
``giulia_bianchi``. That is not a nickname the user chose and it is not information
they agreed to publish -- it is most of their email address. UN-11 says an
address must not be derivable from a username on any unauthenticated surface,
and for a *confirmed* handle that holds because the user picked it. For a
provisional one it holds only for as long as nobody else can see it.

So the question this file answers is narrow and empirical: **can a third party
observe an unconfirmed account's handle?** The findings are recorded as tests
rather than as prose, because prose about a negative goes stale silently.
"""
from __future__ import annotations

import pytest

import crud
import models
import shares
from tests.conftest import client_as, db_client


@pytest.fixture
def provisional(db_session):
    """An account whose handle was derived from its email and never confirmed.

    Created through ``crud.create_user`` with no ``username`` -- the same path
    Google sign-in and the seed scripts take -- so the handle is genuinely
    derived rather than a string this test made up.
    """
    user = crud.create_user(
        db_session, email="giulia.bianchi@clinic.example", email_verified=True
    )
    db_session.commit()
    assert user.username == "giulia_bianchi", (
        "the fixture depends on the handle actually being email-derived"
    )
    assert user.username_confirmed is False
    return user


def test_the_derived_handle_really_does_disclose_the_email(provisional):
    """The premise, stated once so the rest of the file has a reason to exist.

    If the derivation stopped leaking the address, everything below would be
    guarding nothing -- and somebody would eventually delete it as pointless.
    This is the assertion that makes the risk legible.
    """
    local_part = provisional.email.split("@")[0]

    assert provisional.username == local_part.replace(".", "_")


# ---------------------------------------------------------------------------
# The finding, and the fix: publishing is refused while the handle is provisional
# ---------------------------------------------------------------------------
def test_the_share_page_would_publish_an_unconfirmed_handle(
    db_session, provisional, anon
):
    """The leak, demonstrated. This is *why* the checks below exist.

    The share page renders the author's handle -- correctly, since AT-5 and the
    hero block are about crediting a named person. But "named" assumes the name
    was chosen. Given a share on an unconfirmed account's recipe, the page
    publishes ``giulia_bianchi`` to anyone holding the link, and that is most of
    ``giulia.bianchi@clinic.example``.

    The share row is inserted **directly**, bypassing both
    :func:`shares.create_share` and the route, because both now refuse to
    produce it -- which is the fix, and is asserted next door. Reaching the
    state anyway is the point: this is the standing statement of what those
    refusals are protecting, so if a third way to mint a share ever appears,
    this test says what it must not be allowed to enable. Written with the raw
    token in hand rather than by reading one back, since the digest is all the
    row stores.
    """
    recipe = crud.create_recipe(
        db_session,
        title="Ragu della nonna",
        course="main",
        user_id=provisional.id,
    )
    db_session.flush()
    token = shares.mint_token()
    db_session.add(
        models.RecipeShare(
            recipe_id=recipe.id,
            created_by_user_id=provisional.id,
            token_hash=shares.hash_token(token),
            mode="link",
        )
    )
    db_session.commit()

    body = anon.get(f"/s/{token}").text

    # Computed rather than hardcoded, so it survives a change to the fixture.
    assert provisional.email.split("@")[0].replace(".", "_") in body


def test_the_domain_layer_refuses_to_mint_the_share_at_all(db_session, provisional):
    """The rule lives beside the ownership check, not only at the route.

    ``shares.create_share`` already documents why ownership is enforced here
    rather than only at the route -- "the route is a separate layer that could
    grow another caller". UN-11 is the same shape of precondition, and a second
    caller that inherited one check but not the other would publish an email
    local part with nothing to stop it.
    """
    recipe = crud.create_recipe(
        db_session,
        title="Ragu della nonna",
        course="main",
        user_id=provisional.id,
    )
    db_session.flush()

    with pytest.raises(shares.HandleNotConfirmed):
        shares.create_share(
            db_session, recipe=recipe, owner=provisional, mode="link"
        )

    # And VIS-6's promotion did not fire on the refused call.
    assert recipe.visibility == "private"


def test_creating_a_share_is_refused_while_the_handle_is_unconfirmed(
    db_session, provisional
):
    """The server-side enforcement of D-7 -- the point of this whole file.

    ``App.jsx``'s gate stops the *UI* from getting here. It does not stop the
    API, and the account holds a perfectly valid access token: a Google sign-up
    who closes the handle page, or anything scripted, reaches this route with a
    provisional handle intact. Publishing that handle is not a decision the user
    has made, so the route declines to make it for them.

    403 rather than 400: the request is well-formed and the recipe is theirs;
    what is missing is a step the account has not completed. The message names
    that step, because unlike a share-token refusal there is nothing to conceal
    -- the caller is the account in question.
    """
    from main import app

    recipe = crud.create_recipe(
        db_session,
        title="Ragu della nonna",
        course="main",
        user_id=provisional.id,
    )
    db_session.commit()

    client = client_as(db_session, provisional)
    try:
        response = client.post(
            f"/recipes/{recipe.id}/shares", json={"mode": "link"}
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
    assert "username" in response.json()["detail"].lower()


def test_a_refused_share_leaves_the_recipe_private(db_session, provisional):
    """VIS-6 must not fire on a request that was refused.

    Promotion to ``unlisted`` is a side effect of minting a share. If the check
    ran after the domain call rather than before it, the recipe would be left
    advertised as shareable with no share behind it -- and the next share it
    *does* get would skip the promotion.
    """
    from main import app

    recipe = crud.create_recipe(
        db_session,
        title="Ragu della nonna",
        course="main",
        user_id=provisional.id,
    )
    db_session.commit()

    client = client_as(db_session, provisional)
    try:
        client.post(f"/recipes/{recipe.id}/shares", json={"mode": "link"})
    finally:
        app.dependency_overrides.clear()

    db_session.refresh(recipe)
    assert recipe.visibility == "private"
    assert (
        db_session.query(models.RecipeShare).filter_by(recipe_id=recipe.id).all() == []
    )


def test_confirming_the_handle_unblocks_sharing(db_session, provisional):
    """The check is a gate, not a wall.

    Without this, a check that simply refused everyone would pass every test
    above. This is the one that proves the account can get through by doing the
    thing the refusal asks for -- and it is also the regression test for the
    ordinary case, since every normal account is confirmed.
    """
    from main import app
    from datetime import datetime

    recipe = crud.create_recipe(
        db_session,
        title="Ragu della nonna",
        course="main",
        user_id=provisional.id,
    )
    provisional.username_changed_at = datetime.utcnow()
    db_session.commit()

    client = client_as(db_session, provisional)
    try:
        response = client.post(
            f"/recipes/{recipe.id}/shares", json={"mode": "link"}
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201


def test_a_chosen_handle_counts_as_confirmed_from_the_start(db_session):
    """D-7's other half: ``username_changed_at`` records a *choice*.

    ``NULL`` means "system-assigned, unconfirmed". A handle the caller passed in
    was not system-assigned, so leaving it NULL would have said something false
    -- and would have put every locally-registered account behind the gate it
    had just walked through on the registration form (UN-5).
    """
    chosen = crud.create_user(
        db_session, email="chosen@example.com", username="pickedit"
    )
    derived = crud.create_user(db_session, email="derived@example.com")

    assert chosen.username_confirmed is True
    assert derived.username_confirmed is False


def test_another_signed_in_user_cannot_read_an_unconfirmed_handle(
    db_session, provisional, user
):
    """UN-11's other half: a *third party*, not merely an anonymous visitor.

    A signed-in stranger is the more interesting attacker, because they have a
    token and can reach the authenticated API. They must not be able to pull
    another account's provisional handle out of any of it.
    """
    from main import app

    client = client_as(db_session, user)
    try:
        # Nothing addressed to them, so the one route that returns another
        # account's handle has nothing to return.
        shared = client.get("/shared-with-me")
        assert shared.status_code == 200
        assert "giulia_bianchi" not in shared.text

        # And their own account payload is their own.
        me = client.get("/auth/me")
        assert "giulia_bianchi" not in me.text
    finally:
        app.dependency_overrides.clear()


def test_no_route_exposes_another_accounts_handle_by_id(db_session, provisional, user):
    """There is no user-lookup endpoint, and there must not become one.

    UN-10 says no profile page exists yet; the API counterpart is that no route
    turns a user id or handle into an account. Swept rather than listed so a
    future ``GET /users/{id}`` fails here on the day it is added.
    """
    from main import app

    client = client_as(db_session, user)
    try:
        leaks = []
        for route in app.routes:
            path = getattr(route, "path", "")
            methods = getattr(route, "methods", None) or set()
            if "GET" not in methods:
                continue
            target = (
                path.replace("{user_id}", str(provisional.id))
                .replace("{username}", provisional.username)
                .replace("{u}", provisional.username)
            )
            if "{" in target:
                # Not a user-shaped route; covered by the other sweeps.
                continue
            try:
                response = client.get(target, follow_redirects=False)
            except Exception:
                continue
            if "giulia_bianchi" in (response.text or ""):
                leaks.append((target, response.status_code))

        assert leaks == [], f"another account's provisional handle leaked via {leaks}"
    finally:
        app.dependency_overrides.clear()


def test_the_availability_endpoint_does_not_confirm_a_provisional_handle(
    provisional, anon
):
    """UN-7's oracle, checked against the *unconfirmed* case.

    ``GET /usernames/available`` is unauthenticated and answers "taken" for a
    handle in use -- which is correct and necessary for the sign-up form. It is
    worth pinning that this is all it says: a caller who guesses ``giulia_bianchi``
    learns that somebody holds it, which they could also learn by trying to
    register it, and specifically does not learn an email, an id, or that the
    holder is an unconfirmed account whose handle was derived rather than
    chosen. That last distinction is the one that would turn the endpoint into
    an email-guessing oracle: "is ``giulia_bianchi`` a *derived* handle" is very
    nearly "does ``giulia.bianchi@`` have an account here".
    """
    response = anon.get("/usernames/available", params={"u": "giulia_bianchi"})

    assert response.status_code == 200
    body = response.json()
    assert body["available"] is False
    assert body["reason"] == "taken"
    # Two fields, and neither of them says "unconfirmed" or "derived".
    assert set(body) == {"available", "reason"}
    assert "clinic.example" not in response.text
