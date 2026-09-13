"""TST-7: multi-user isolation for the catalog.

User A's adoption is invisible to user B except through the aggregate count
(PRV-1, PRV-2). Modelled on ``tests/test_multiuser_isolation.py``: one test
session, with the client re-pointed between accounts via ``client_as``.
"""

import pytest

from main import app
from tests.conftest import client_as


@pytest.fixture
def adopted(db_session, user, other_user, make_catalog_recipe):
    """``user`` (A) has adopted one catalog recipe; returns ``(source, copy_id)``."""
    source = make_catalog_recipe("Shared favourite")
    make_catalog_recipe("Untouched")
    try:
        client = client_as(db_session, user)
        response = client.post("/catalog/adopt", json={"recipe_ids": [source.id]})
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    [copy_id] = response.json()["created_ids"]
    return source, copy_id


@pytest.fixture
def as_b(db_session, other_user):
    try:
        yield client_as(db_session, other_user)
    finally:
        app.dependency_overrides.clear()


def _row(response, recipe_id):
    assert response.status_code == 200
    [row] = [r for r in response.json() if r["id"] == recipe_id]
    return row


def test_b_sees_the_count_but_not_that_it_is_in_their_book(adopted, as_b, user):
    source, copy_id = adopted

    listing = as_b.get("/catalog/recipes")
    row = _row(listing, source.id)
    assert row["adoption_count"] == 1
    assert row["in_my_book"] is False
    assert copy_id not in {r["id"] for r in listing.json()}

    detail = as_b.get(f"/catalog/recipes/{source.id}").json()
    assert detail["adoption_count"] == 1
    assert detail["in_my_book"] is False

    for body in (listing.text, as_b.get(f"/catalog/recipes/{source.id}").text):
        assert user.username not in body
        assert user.email not in body


def test_b_cannot_reach_as_copy_through_any_catalog_route(adopted, as_b):
    _, copy_id = adopted

    assert as_b.get(f"/catalog/recipes/{copy_id}").status_code == 404
    assert as_b.post("/catalog/adopt", json={"recipe_ids": [copy_id]}).status_code == 404


def test_b_cannot_reach_as_copy_through_the_recipe_routes(adopted, as_b):
    _, copy_id = adopted

    assert copy_id not in {r["id"] for r in as_b.get("/recipes").json()}
    assert as_b.get(f"/recipes/{copy_id}").status_code == 404


def test_as_view_is_unaffected_by_bs_adoption(db_session, adopted, user, other_user):
    source, copy_id = adopted
    try:
        as_b = client_as(db_session, other_user)
        assert as_b.post("/catalog/adopt", json={"recipe_ids": [source.id]}).status_code == 200

        as_a = client_as(db_session, user)
        row = _row(as_a.get("/catalog/recipes"), source.id)
        own = as_a.get("/recipes").json()
    finally:
        app.dependency_overrides.clear()

    assert row["in_my_book"] is True
    assert row["adoption_count"] == 2
    assert [r["id"] for r in own] == [copy_id]
