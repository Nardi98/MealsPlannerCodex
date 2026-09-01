"""FC-9 / FC-10 / RA-9: this release must leave no indexable surface behind.

The requirement is a *negative* one -- "the decision to publish user content to
the open web MUST remain unmade and reversible" -- and negative requirements rot
silently. Nothing breaks when somebody adds a route that search engines are
happy to crawl; the product simply stops being un-published, and nobody notices
until the content is in an index and the decision has been made by accident.
So the assertions here are deliberately *structural* rather than a list of
today's URLs: the sweep walks ``app.routes`` and holds whatever it finds to the
rule, which means a route added next month is covered the day it is added.

Interpretation of FC-10, recorded rather than hidden
----------------------------------------------------
FC-10 as written says "no route in this release returns a page lacking
``noindex``". Taken literally that includes ``/recipes`` returning JSON, where
``noindex`` is meaningless -- a crawler does not index a JSON API response as a
page, and ``X-Robots-Tag`` on it communicates nothing. The rule is therefore
scoped to responses that are actually *pages*: anything served as
``text/html``. This is the interpretation the plan records, and it is the one
that has teeth, because the HTML surfaces are exactly the ones a crawler would
render.
"""
from __future__ import annotations

import pytest
from fastapi.routing import APIRoute

import crud
import models
import shares
from tests.conftest import get_route_paths


#: Paths a discovery-oriented crawler (or a curious human) would try first.
#: Every one of them must be a plain 404: not an empty document, not a redirect,
#: not a 405. ``/@handle`` and ``/profiles/{handle}`` are the two shapes a
#: future profile page would plausibly take, and UN-10 says no profile page
#: exists yet -- asserting they 404 is what keeps "no profile page" true.
DISCOVERY_PATHS = [
    "/sitemap.xml",
    "/robots.txt",
    "/search",
    "/@owner",
    "/profiles/owner",
    "/profile/owner",
    "/users/owner",
]

#: Markup that declares a page's content to an indexer. RA-9 forbids all of it:
#: structured data and a canonical link are *invitations* to index, and this
#: release is not issuing any.
INDEXING_SIGNALS = [
    "application/ld+json",
    'rel="canonical"',
    "rel='canonical'",
    "schema.org",
    "itemscope",
    "itemtype",
]


def _is_noindexed(response) -> bool:
    """Whether ``response`` tells crawlers to stay away.

    Either channel counts. The ``X-Robots-Tag`` header is the stronger of the
    two -- it is honoured for non-HTML bodies and cannot be stripped by a
    partial render -- but a ``<meta name="robots">`` tag is the conventional
    one and is what a human reviewer looks for in view-source, so a page
    carrying only that still satisfies the requirement.
    """
    header = response.headers.get("x-robots-tag", "").lower()
    if "noindex" in header:
        return True
    body = (response.text or "").lower()
    return 'name="robots"' in body and "noindex" in body


@pytest.fixture
def shared_page(db_session, user):
    """A live link share, and the HTML its page renders.

    A real rendered page rather than a fixture string: the assertions below are
    about what a crawler would actually receive, and a hand-written sample
    would keep passing after the template started emitting JSON-LD.
    """
    recipe = crud.create_recipe(
        db_session,
        title="Pasta al pomodoro",
        course="main",
        procedure="Boil the pasta. Add sauce.",
        user_id=user.id,
    )
    ingredient = crud.create_ingredient(
        db_session,
        name="pasta",
        season_months=[],
        user_id=user.id,
    )
    db_session.add(
        models.RecipeIngredient(
            recipe_id=recipe.id, ingredient_id=ingredient.id, quantity=200.0
        )
    )
    db_session.commit()
    _, token = shares.create_share(
        db_session, recipe=recipe, owner=user, mode="link"
    )
    db_session.commit()
    return token


# ---------------------------------------------------------------------------
# FC-10: every page carries noindex
# ---------------------------------------------------------------------------
def test_every_html_route_is_noindexed(anon):
    """The sweep. Any HTML response from any GET route must carry ``noindex``.

    Written as a sweep with a collected failure list rather than a
    parametrised case per path so that the failure message names *every*
    offending route at once -- the useful output when someone adds two.
    """
    from main import app

    offenders = []
    for path in get_route_paths(app, parameterised=False):
        response = anon.get(path, follow_redirects=False)
        content_type = response.headers.get("content-type", "")
        if "text/html" not in content_type:
            continue
        if not _is_noindexed(response):
            offenders.append((path, response.status_code))

    assert offenders == [], (
        "HTML routes served without a noindex signal (FC-9/FC-10): "
        f"{offenders}. Every page this release serves must tell crawlers to "
        "stay away; see the X-Robots-Tag middleware in main.py."
    )


def test_the_share_page_itself_is_noindexed(anon, shared_page):
    """The one HTML route with a path parameter, covered explicitly."""
    response = anon.get(f"/s/{shared_page}")

    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    assert _is_noindexed(response)


def test_the_share_pages_neutral_404_is_also_noindexed(anon):
    """A 404 body is still a body a crawler can be served."""
    response = anon.get("/s/not-a-real-token")

    assert response.status_code == 404
    assert "noindex" in response.headers.get("x-robots-tag", "").lower()


# ---------------------------------------------------------------------------
# FC-9: no discovery endpoint exists
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("path", DISCOVERY_PATHS)
def test_no_discovery_endpoint_exists(anon, path):
    """Sitemaps, robots.txt, search, and profile URLs are all simply absent.

    ``robots.txt`` returning 404 rather than a ``Disallow: /`` file is the
    right answer here and worth stating: a served ``robots.txt`` is a
    *published* crawl policy and therefore a public statement that the site
    expects crawlers. FC-9 wants no such statement -- the ``noindex`` above is
    per-page, honoured by well-behaved crawlers, and does not advertise
    anything about the surfaces it does not name.
    """
    response = anon.get(path, follow_redirects=False)

    assert response.status_code == 404, (
        f"{path} exists (status {response.status_code}); FC-9 forbids "
        "introducing any public discovery endpoint in this release."
    )


def test_no_route_is_registered_under_a_discovery_path():
    """The same rule at the routing table, not just at the response.

    A route registered but currently failing its auth check would 404 above
    while still existing; this is the assertion that catches it being wired up
    at all.
    """
    from main import app

    registered = {getattr(route, "path", "") for route in app.routes}
    forbidden = {"/sitemap.xml", "/robots.txt", "/search"}

    assert registered & forbidden == set()


def test_no_route_is_mounted_under_a_username_shaped_prefix():
    """No ``/@{handle}`` or ``/profiles/{handle}`` route (UN-10, FC-9)."""
    from main import app

    for route in app.routes:
        path = getattr(route, "path", "")
        assert not path.startswith("/@"), f"profile-shaped route: {path}"
        assert not path.startswith("/profiles"), f"profile-shaped route: {path}"


# ---------------------------------------------------------------------------
# RA-9: no structured data, no canonical
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("signal", INDEXING_SIGNALS)
def test_the_share_page_emits_no_indexing_signal(anon, shared_page, signal):
    response = anon.get(f"/s/{shared_page}")

    assert signal.lower() not in response.text.lower(), (
        f"the share page emits {signal!r}; RA-9 forbids structured data, a "
        "canonical link, or any other indexing signal."
    )


def test_the_share_page_template_source_emits_no_indexing_signal():
    """Belt and braces: the template can carry a signal a fixture never hits.

    A conditional ``{% if %}`` around JSON-LD would render nothing for this
    fixture's recipe and everything for one with an image and a rating. Reading
    the template source catches that; rendering one recipe does not.

    Jinja comments are stripped before scanning. The template's own header says
    "no canonical, no schema.org" -- a comment *documenting* the prohibition is
    not a violation of it, and matching on it would make this test impossible
    to satisfy without deleting the explanation.
    """
    import os
    import re

    import public_pages

    templates_dir = os.path.join(
        os.path.dirname(os.path.abspath(public_pages.__file__)), "templates"
    )
    sources = []
    for root, _dirs, files in os.walk(templates_dir):
        for name in files:
            with open(os.path.join(root, name), encoding="utf-8") as handle:
                source = re.sub(r"\{#.*?#\}", "", handle.read(), flags=re.S)
            sources.append((os.path.join(root, name), source.lower()))

    assert sources, "no templates found; the path above is wrong"
    for path, source in sources:
        for signal in INDEXING_SIGNALS:
            assert signal.lower() not in source, f"{path} contains {signal!r}"


def test_the_share_route_is_absent_from_the_public_schema():
    """RA-8/FC-9: the one public page is not advertised in the API docs.

    ``/s/{token}`` takes a capability in its path. Listing it in a schema that
    ``/docs`` renders for anyone would publish the *shape* of the sharing
    system to an unauthenticated reader -- pointless, since the token is the
    only thing that matters, and it hands a scanner a target.
    """
    from main import app

    route = next(
        r for r in app.routes
        if isinstance(r, APIRoute) and r.path == "/s/{token}"
    )

    assert route.include_in_schema is False
