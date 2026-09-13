"""The user-facing catalog routes: browse, detail and adopt (spec §10.1, §8, §13, §16).

Every test builds on ``make_catalog_recipe`` (and so ``system_account``), which
empties the catalog inside the test's transaction, so assertions are about rows
the test created, never about whatever the bootstrap may have loaded.
"""

import logging
from contextlib import contextmanager

import pytest
from sqlalchemy import event, func, select, update

import catalog
import crud
import models
import schemas
from main import app
from tests.conftest import client_as

ROW_KEYS = {
    "id", "title", "course", "servings", "bulk_prep", "image_url",
    "tags", "ingredients", "adoption_count", "in_my_book",
}
DETAIL_KEYS = ROW_KEYS | {"procedure"}
INGREDIENT_KEYS = {"name", "quantity", "unit"}

#: API-2/4/8 and PRV-3: none of these may appear anywhere in a catalog body.
FORBIDDEN_KEYS = {
    "procedure", "score", "date_last_consumed", "date_last_rejected",
    "copy_count", "visibility", "user_id", "email", "username",
    "source_user_id", "source_author_username", "owner",
}

#: Integer fields whose value is legitimately *not* an account id, so a
#: coincidental match with the system account's id means nothing.
_NUMERIC_FIELDS = {"id", "adoption_count", "servings", "quantity", "created_ids", "skipped_ids"}


@pytest.fixture
def client(db_session, user):
    try:
        yield client_as(db_session, user)
    finally:
        app.dependency_overrides.clear()


def _walk(value, key=None):
    """Yield every ``(key, leaf)`` pair of a JSON document."""
    if isinstance(value, dict):
        for k, v in value.items():
            yield k, v
            yield from _walk(v, k)
    elif isinstance(value, list):
        for item in value:
            yield from _walk(item, key)
    else:
        yield key, value


def assert_no_system_identity(body, system):
    """API-7 / PRV-3: the system account's handle, email and id are nowhere."""
    assert "mealplanner" not in str(body).lower()
    for key, leaf in _walk(body):
        assert key not in FORBIDDEN_KEYS
        if isinstance(leaf, str):
            assert system.email not in leaf and system.username not in leaf
        if isinstance(leaf, int) and not isinstance(leaf, bool) and key not in _NUMERIC_FIELDS:
            assert leaf != system.id, f"system id under {key!r}"


@contextmanager
def count_queries(session):
    statements = []
    engine = session.get_bind().engine

    def _record(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", _record)
    try:
        yield statements
    finally:
        event.remove(engine, "before_cursor_execute", _record)


def _titles(response):
    assert response.status_code == 200, response.text
    return [row["title"] for row in response.json()]


def _recipe_count(db_session, owner):
    return db_session.execute(
        select(func.count()).select_from(models.Recipe).where(models.Recipe.user_id == owner.id)
    ).scalar_one()


# --- Listing (API-1..4, API-7/8) --------------------------------------------


def test_listing_rows_carry_exactly_the_allowlisted_keys(client, make_catalog_recipe, system_account):
    make_catalog_recipe(
        "Pasta al pomodoro",
        ingredients=(("Pasta", 80, "g"), ("Tomato passata", 100, "ml"), ("Egg", 1, "piece")),
        tags=("pasta", "quick"),
        servings=2,
        bulk_prep=True,
    )

    response = client.get("/catalog/recipes")

    assert response.status_code == 200
    [row] = response.json()
    assert set(row) == ROW_KEYS
    assert row["title"] == "Pasta al pomodoro"
    assert row["course"] == "main"
    assert row["servings"] == 2
    assert row["bulk_prep"] is True
    assert row["image_url"] is None
    assert sorted(row["tags"]) == ["pasta", "quick"]
    assert row["adoption_count"] == 0
    assert row["in_my_book"] is False
    for ingredient in row["ingredients"]:
        assert set(ingredient) == INGREDIENT_KEYS
    assert sorted((i["name"], i["quantity"], i["unit"]) for i in row["ingredients"]) == [
        ("Egg", 1, "piece"), ("Pasta", 80, "g"), ("Tomato passata", 100, "ml"),
    ]


def test_listing_never_exposes_the_system_account(client, make_catalog_recipe, system_account):
    make_catalog_recipe("Minestrone")

    response = client.get("/catalog/recipes")

    assert response.status_code == 200
    assert "mealplanner" not in response.text
    assert_no_system_identity(response.json(), system_account)


def test_course_is_repeatable_and_ored(client, make_catalog_recipe):
    make_catalog_recipe("Main one", course="main")
    make_catalog_recipe("Side one", course="side")
    make_catalog_recipe("First one", course="first-course")

    titles = _titles(client.get("/catalog/recipes?course=main&course=side&sort=title"))

    assert titles == ["Main one", "Side one"]


def test_tags_are_repeatable_and_anded(client, make_catalog_recipe):
    make_catalog_recipe("Both", tags=("vegan", "quick"))
    make_catalog_recipe("Only vegan", tags=("vegan",))
    make_catalog_recipe("Only quick", tags=("quick",))

    assert _titles(client.get("/catalog/recipes?tags=vegan&tags=quick")) == ["Both"]


def test_q_is_a_case_insensitive_title_substring(client, make_catalog_recipe):
    make_catalog_recipe("Pasta e fagioli")
    make_catalog_recipe("Risotto")

    assert _titles(client.get("/catalog/recipes?q=PASTA")) == ["Pasta e fagioli"]


def test_sort_popular_and_title(client, db_session, make_catalog_recipe, other_user):
    make_catalog_recipe("Apple pie")
    popular = make_catalog_recipe("Zucchini fritters")
    catalog.adopt(db_session, other_user, [popular.id])

    assert _titles(client.get("/catalog/recipes")) == ["Zucchini fritters", "Apple pie"]
    assert _titles(client.get("/catalog/recipes?sort=popular")) == ["Zucchini fritters", "Apple pie"]
    assert _titles(client.get("/catalog/recipes?sort=title")) == ["Apple pie", "Zucchini fritters"]


def test_an_unknown_sort_is_a_client_error_not_a_500(client, make_catalog_recipe):
    make_catalog_recipe("Anything")

    response = client.get("/catalog/recipes?sort=newest")

    assert response.status_code == 422


def test_listing_hides_retired_entries(client, make_catalog_recipe):
    make_catalog_recipe("Live")
    make_catalog_recipe("Gone", status="retired")

    assert _titles(client.get("/catalog/recipes")) == ["Live"]


def test_in_my_book_flips_after_adopting(client, make_catalog_recipe):
    recipe = make_catalog_recipe("Carbonara")
    [before] = client.get("/catalog/recipes").json()
    assert before["in_my_book"] is False
    assert before["adoption_count"] == 0

    assert client.post("/catalog/adopt", json={"recipe_ids": [recipe.id]}).status_code == 200

    [after] = client.get("/catalog/recipes").json()
    assert after["in_my_book"] is True
    assert after["adoption_count"] == 1


def test_listing_statement_count_does_not_grow_with_rows(client, db_session, make_catalog_recipe):
    """API-3 / CAT-5: rows and ``in_my_book`` are one query each for the whole listing."""
    make_catalog_recipe("One", tags=("a", "b"))
    client.get("/catalog/recipes")  # warm anything lazily initialised
    with count_queries(db_session) as one_row:
        assert len(client.get("/catalog/recipes").json()) == 1

    for n in range(4):
        make_catalog_recipe(f"More {n}", ingredients=(("Pasta", 80, "g"), ("Rice", 50, "g")), tags=("c",))
    with count_queries(db_session) as five_rows:
        assert len(client.get("/catalog/recipes").json()) == 5

    assert len(five_rows) == len(one_row)


# --- Detail (API-5) -----------------------------------------------------------


def test_detail_adds_the_procedure(client, make_catalog_recipe, system_account):
    recipe = make_catalog_recipe("Frittata", procedure="Beat the eggs.")

    response = client.get(f"/catalog/recipes/{recipe.id}")

    assert response.status_code == 200
    body = response.json()
    assert set(body) == DETAIL_KEYS
    assert body["procedure"] == "Beat the eggs."
    assert body["in_my_book"] is False
    assert body["adoption_count"] == 0
    assert "mealplanner" not in response.text


def test_detail_404_for_a_retired_entry(client, make_catalog_recipe):
    recipe = make_catalog_recipe("Retired", status="retired")

    assert client.get(f"/catalog/recipes/{recipe.id}").status_code == 404


def test_detail_404_for_an_uncatalogued_system_recipe(client, db_session, system_account):
    recipe = models.Recipe(user_id=system_account.id, title="Draft", procedure="x")
    db_session.add(recipe)
    db_session.flush()

    assert client.get(f"/catalog/recipes/{recipe.id}").status_code == 404


def test_detail_404_for_another_users_recipe(client, db_session, system_account, other_user):
    recipe = crud.create_recipe(db_session, title="Theirs", user_id=other_user.id)

    assert client.get(f"/catalog/recipes/{recipe.id}").status_code == 404


# --- Adopt (API-6, §8, ERR-1..4, ERR-12, PRV-6) ------------------------------


def test_adopt_reports_created_and_skipped(client, db_session, user, make_catalog_recipe):
    held = make_catalog_recipe("Already mine")
    fresh = make_catalog_recipe("New to me")
    catalog.adopt(db_session, user, [held.id])

    response = client.post("/catalog/adopt", json={"recipe_ids": [held.id, fresh.id]})

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"created_ids", "skipped_ids"}
    assert body["skipped_ids"] == [held.id]
    [created_id] = body["created_ids"]
    copy = db_session.get(models.Recipe, created_id)
    assert copy.user_id == user.id
    assert copy.source_recipe_id == fresh.id


def test_adopt_rejects_an_empty_list(client, make_catalog_recipe):
    make_catalog_recipe("Anything")

    response = client.post("/catalog/adopt", json={"recipe_ids": []})

    assert response.status_code == 400
    assert response.json()["detail"]


def test_adopt_rejects_more_than_the_batch_limit_naming_it(client, make_catalog_recipe):
    recipe = make_catalog_recipe("Anything")
    ids = [recipe.id] + list(range(10**6, 10**6 + catalog.ADOPT_BATCH_MAX))

    response = client.post("/catalog/adopt", json={"recipe_ids": ids})

    assert response.status_code == 400
    assert str(catalog.ADOPT_BATCH_MAX) in response.json()["detail"]


def test_adopt_404_for_a_non_published_id_creates_nothing(client, db_session, user, make_catalog_recipe):
    live = make_catalog_recipe("Live")
    retired = make_catalog_recipe("Retired", status="retired")

    response = client.post("/catalog/adopt", json={"recipe_ids": [live.id, retired.id]})

    assert response.status_code == 404
    assert _recipe_count(db_session, user) == 0


def test_repeating_a_batch_skips_everything(client, db_session, user, make_catalog_recipe):
    ids = sorted([make_catalog_recipe("A").id, make_catalog_recipe("B").id])

    first = client.post("/catalog/adopt", json={"recipe_ids": ids}).json()
    second = client.post("/catalog/adopt", json={"recipe_ids": ids}).json()

    assert len(first["created_ids"]) == 2 and first["skipped_ids"] == []
    assert second == {"created_ids": [], "skipped_ids": ids}
    assert _recipe_count(db_session, user) == 2


def test_adopt_404_for_another_users_recipe(client, db_session, user, system_account, other_user):
    theirs = crud.create_recipe(db_session, title="Theirs", user_id=other_user.id)

    response = client.post("/catalog/adopt", json={"recipe_ids": [theirs.id]})

    assert response.status_code == 404
    assert _recipe_count(db_session, user) == 0


def test_adopt_404_for_a_users_copy_of_a_catalog_recipe(
    client, db_session, user, other_user, make_catalog_recipe
):
    source = make_catalog_recipe("Lasagne")
    [their_copy] = catalog.adopt(db_session, other_user, [source.id]).created_ids

    response = client.post("/catalog/adopt", json={"recipe_ids": [their_copy]})

    assert response.status_code == 404
    assert _recipe_count(db_session, user) == 0


def test_adopt_is_rate_limited_per_user(db_session, user, other_user, make_catalog_recipe, monkeypatch):
    """ADO-13: the per-user ``ratelimit.limiter``, so one user's budget is not another's."""
    import auth_users

    recipe = make_catalog_recipe("Popular")
    monkeypatch.setattr(app.state.share_limiter, "enabled", True)

    def adopt_as(account):
        client = client_as(db_session, account)
        token = auth_users.create_access_token(str(account.id))
        return client.post(
            "/catalog/adopt",
            json={"recipe_ids": [recipe.id]},
            headers={"Authorization": f"Bearer {token}"},
        ).status_code

    try:
        statuses = []
        for _ in range(60):
            statuses.append(adopt_as(user))
            if statuses[-1] == 429:
                break
        other_status = adopt_as(other_user)
    finally:
        app.dependency_overrides.clear()

    assert statuses[-1] == 429
    assert set(statuses[:-1]) == {200}
    assert other_status == 200


# --- Authentication (P2-4) ----------------------------------------------------


@pytest.mark.parametrize(
    ("method", "path"),
    [("GET", "/catalog/recipes"), ("GET", "/catalog/recipes/{id}"), ("POST", "/catalog/adopt")],
)
def test_every_catalog_route_requires_authentication(anon, make_catalog_recipe, method, path):
    recipe = make_catalog_recipe("Guarded")

    response = anon.request(
        method,
        path.replace("{id}", str(recipe.id)),
        json={"recipe_ids": [recipe.id]} if method == "POST" else None,
    )

    assert response.status_code == 401


# --- ERR-5 ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("method", "path"),
    [("GET", "/catalog/recipes"), ("GET", "/catalog/recipes/{id}"), ("POST", "/catalog/adopt")],
)
def test_a_missing_system_account_is_a_named_500(client, db_session, make_catalog_recipe, caplog, method, path):
    recipe = make_catalog_recipe("Orphaned")
    recipe_id = recipe.id
    # "No is_system row" is the condition ERR-5 names. Clearing the flag rather
    # than deleting the row keeps the published entry in place, so a 500 here
    # cannot be a listing that merely came back empty.
    db_session.execute(
        update(models.User).where(models.User.is_system.is_(True)).values(is_system=False)
    )
    db_session.expire_all()

    with caplog.at_level(logging.ERROR):
        response = client.request(
            method,
            path.replace("{id}", str(recipe_id)),
            json={"recipe_ids": [recipe_id]} if method == "POST" else None,
        )

    assert response.status_code == 500
    assert "mealplanner" not in response.text
    assert any(
        record.levelno == logging.ERROR and "no is_system account" in record.getMessage()
        for record in caplog.records
    )


# --- API-16 / API-17 ------------------------------------------------------------


def test_the_adopted_copy_is_from_the_library_and_system_recipes_stay_out(
    client, db_session, make_catalog_recipe
):
    adopted = make_catalog_recipe("Adopted dish")
    make_catalog_recipe("Not adopted")
    [copy_id] = client.post("/catalog/adopt", json={"recipe_ids": [adopted.id]}).json()["created_ids"]

    response = client.get("/recipes")

    assert response.status_code == 200
    rows = response.json()
    assert [row["id"] for row in rows] == [copy_id]
    [row] = rows
    assert row["title"] == "Adopted dish"
    assert row["from_library"] is True
    assert row["source_author_username"] is None
    assert "mealplanner" not in response.text

    detail = client.get(f"/recipes/{copy_id}")
    assert detail.status_code == 200
    assert detail.json()["from_library"] is True
    assert detail.json()["source_author_username"] is None
    assert client.get(f"/recipes/{adopted.id}").status_code == 404


# --- TST-5 / P2-2 / P2-3 ----------------------------------------------------------


def test_public_visibility_is_still_rejected(client):
    response = client.post(
        "/recipes", json={"title": "Try public", "course": "main", "visibility": "public"}
    )

    assert response.status_code == 400
    assert schemas.PUBLIC_VISIBILITY_MESSAGE in response.text


def test_every_catalog_recipe_and_copy_is_private(client, db_session, make_catalog_recipe):
    ids = [make_catalog_recipe("One").id, make_catalog_recipe("Two", status="retired").id]
    client.post("/catalog/adopt", json={"recipe_ids": ids[:1]})

    catalogued = db_session.execute(
        select(models.Recipe.visibility).join(models.Recipe.catalog_entry)
    ).scalars().all()
    copies = db_session.execute(
        select(models.Recipe.visibility).where(models.Recipe.source_recipe_id.in_(ids))
    ).scalars().all()

    assert len(catalogued) == 2 and len(copies) == 1
    assert set(catalogued) | set(copies) == {"private"}
