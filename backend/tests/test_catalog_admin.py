"""Admin catalog curation: service and routes (spec §9, §10.2, §13, §16, plan D3).

Every test builds on ``system_account`` (directly or through
``make_catalog_recipe``), which empties the catalog inside the test's
transaction, so assertions are about rows the test created.

The write routes commit on success and roll back on failure, which the shared
``db_session`` scopes to a SAVEPOINT (see ``conftest.py``). A test
asserting that a failed write left nothing behind first commits its fixtures,
so the route's rollback cannot take them with it.
"""

import logging
from datetime import datetime

import pytest
from sqlalchemy import func, select, update

import catalog
import catalog_admin_routes
import crud
import models
from main import app
from tests.conftest import client_as, db_client

ADMIN_ROW_KEYS = {
    "id", "title", "course", "servings", "bulk_prep", "image_url", "tags",
    "ingredients", "adoption_count", "procedure", "status", "published_at", "retired_at",
}
INGREDIENT_KEYS = {"name", "quantity", "unit"}
MISSING_ID = 10**9

#: The Contracts' admin route table, exactly (plan "Admin HTTP").
CONTRACT_ROUTES = {
    ("GET", "/admin/catalog/recipes"),
    ("POST", "/admin/catalog/recipes"),
    ("PUT", "/admin/catalog/recipes/{recipe_id}"),
    ("POST", "/admin/catalog/recipes/{recipe_id}/publish"),
    ("POST", "/admin/catalog/recipes/{recipe_id}/retire"),
    ("GET", "/admin/catalog/export"),
    ("GET", "/admin/catalog/ingredients"),
    ("GET", "/admin/catalog/tags"),
}
WRITE_ROUTES = sorted(
    (method, path) for method, path in CONTRACT_ROUTES if method in {"POST", "PUT"}
)


def _router_table():
    """Every ``(method, path)`` the admin router actually serves."""
    return sorted(
        (method, route.path)
        for route in catalog_admin_routes.router.routes
        for method in route.methods
    )


ROUTER_TABLE = _router_table()


@pytest.fixture
def admin(db_session, admin_user, system_account):
    try:
        yield client_as(db_session, admin_user)
    finally:
        app.dependency_overrides.clear()


def recipe_body(**overrides):
    body = {
        "title": "Admin risotto",
        "course": "first-course",
        "servings": 2,
        "bulk_prep": True,
        "procedure": "Toast the rice, then stir in stock.",
        "image_url": None,
        "tags": ["rice", "quick"],
        "ingredients": [
            {"name": "Rice", "quantity": 160, "unit": "g"},
            {"name": "Onion", "quantity": 1, "unit": "piece"},
        ],
    }
    body.update(overrides)
    return body


def _fill(path, recipe_id):
    return path.replace("{recipe_id}", str(recipe_id))


def _call(client, method, path, recipe_id):
    """Call one route with a valid body wherever the route could take one."""
    return client.request(
        method,
        _fill(path, recipe_id),
        json=recipe_body() if method in {"POST", "PUT"} else None,
    )


def _count(session, model, owner):
    return session.scalar(
        select(func.count()).select_from(model).where(model.user_id == owner.id)
    )


def _names(rows):
    return sorted((line["name"], line["quantity"], line["unit"]) for line in rows)


# --- Route table (API-14, API-15, ADM-4) --------------------------------------


def test_the_router_serves_exactly_the_contract_routes():
    assert set(ROUTER_TABLE) == CONTRACT_ROUTES


def test_no_delete_route_exists_under_admin_catalog():
    """API-14 / RET-5: over every method, on the router and on the mounted app."""
    assert all(method != "DELETE" for method, _ in ROUTER_TABLE)
    for route in app.routes:
        if getattr(route, "path", "").startswith("/admin/catalog"):
            assert "DELETE" not in (getattr(route, "methods", None) or set())


def test_every_admin_route_depends_on_require_admin():
    import auth_users

    assert any(dep.dependency is auth_users.require_admin for dep in catalog_admin_routes.router.dependencies)


@pytest.mark.parametrize(("method", "path"), ROUTER_TABLE)
def test_every_admin_route_is_401_for_anonymous_callers(db_session, make_catalog_recipe, method, path):
    recipe = make_catalog_recipe("Guarded")
    try:
        response = _call(db_client(db_session), method, path, recipe.id)
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 401


@pytest.mark.parametrize(("method", "path"), ROUTER_TABLE)
def test_every_admin_route_is_one_identical_403_for_a_non_admin(
    db_session, user, make_catalog_recipe, method, path
):
    """ERR-8 / PRV-5: the same body whether the recipe exists or not."""
    recipe = make_catalog_recipe("Guarded")
    client = client_as(db_session, user)
    try:
        existing = _call(client, method, path, recipe.id)
        missing = _call(client, method, path, MISSING_ID)
    finally:
        app.dependency_overrides.clear()

    assert existing.status_code == missing.status_code == 403
    assert existing.json() == {"detail": "Forbidden"}
    assert existing.content == missing.content
    assert existing.headers.get("content-type") == missing.headers.get("content-type")


# --- Create (API-10, ADM-7, ADM-12, D3, ERR-6) ----------------------------------


def test_create_makes_a_system_owned_published_private_recipe(admin, db_session, system_account):
    response = admin.post("/admin/catalog/recipes", json=recipe_body())

    assert response.status_code == 201, response.text
    row = response.json()
    assert set(row) == ADMIN_ROW_KEYS
    assert row["title"] == "Admin risotto"
    assert row["course"] == "first-course"
    assert row["servings"] == 2
    assert row["bulk_prep"] is True
    assert row["procedure"] == "Toast the rice, then stir in stock."
    assert sorted(row["tags"]) == ["quick", "rice"]
    assert _names(row["ingredients"]) == [("Onion", 1, "piece"), ("Rice", 160, "g")]
    assert all(set(line) == INGREDIENT_KEYS for line in row["ingredients"])
    assert row["status"] == "published"
    assert row["adoption_count"] == 0
    assert datetime.fromisoformat(row["published_at"])
    assert row["retired_at"] is None

    recipe = db_session.get(models.Recipe, row["id"])
    assert recipe.user_id == system_account.id
    assert recipe.visibility == "private"
    assert recipe.catalog_entry.status == "published"
    assert {line.ingredient.user_id for line in recipe.ingredients} == {system_account.id}
    assert {tag.user_id for tag in recipe.tags} == {system_account.id}


def test_create_with_publish_false_makes_a_draft_with_no_entry(admin, db_session, system_account):
    response = admin.post("/admin/catalog/recipes", json={**recipe_body(), "publish": False})

    assert response.status_code == 201, response.text
    row = response.json()
    assert set(row) == ADMIN_ROW_KEYS
    assert row["status"] is None
    assert row["published_at"] is None and row["retired_at"] is None
    recipe = db_session.get(models.Recipe, row["id"])
    assert recipe.user_id == system_account.id
    assert recipe.catalog_entry is None
    # A draft is not an entry, so the entry listing does not show it (API-9).
    assert row["id"] not in {r["id"] for r in admin.get("/admin/catalog/recipes").json()}


def test_create_touches_neither_the_admins_pantry_nor_the_system_vocabulary(
    admin, db_session, admin_user, system_account
):
    """ADM-7 / ADM-12: names resolve onto existing system rows; nothing is created."""
    crud.get_or_create_ingredient(db_session, None, "Rice", admin_user.id)
    crud.get_or_create_tag(db_session, "rice", admin_user.id)
    db_session.flush()
    before = {
        "admin_ingredients": _count(db_session, models.Ingredient, admin_user),
        "admin_tags": _count(db_session, models.Tag, admin_user),
        "system_ingredients": _count(db_session, models.Ingredient, system_account),
        "system_tags": _count(db_session, models.Tag, system_account),
    }

    response = admin.post("/admin/catalog/recipes", json=recipe_body())

    assert response.status_code == 201, response.text
    after = {
        "admin_ingredients": _count(db_session, models.Ingredient, admin_user),
        "admin_tags": _count(db_session, models.Tag, admin_user),
        "system_ingredients": _count(db_session, models.Ingredient, system_account),
        "system_tags": _count(db_session, models.Tag, system_account),
    }
    assert after == before
    assert _count(db_session, models.Recipe, admin_user) == 0


@pytest.mark.parametrize(
    ("overrides", "detail"),
    [
        ({"ingredients": [{"name": "Rice", "quantity": 1, "unit": "g"},
                          {"name": "Unobtainium", "quantity": 1, "unit": "g"}]},
         "Unknown ingredient: Unobtainium"),
        ({"tags": ["rice", "no-such-tag"]}, "Unknown tag: no-such-tag"),
        # Matching is exact, as ``crud.get_or_create_ingredient``'s lookup is.
        ({"ingredients": [{"name": "rice", "quantity": 1, "unit": "g"}]}, "Unknown ingredient: rice"),
        # One line per ingredient: a repeat is a 400, not a primary-key 500.
        ({"ingredients": [{"name": "Rice", "quantity": 1, "unit": "g"},
                          {"name": "Rice", "quantity": 2, "unit": "g"}]},
         "Duplicate ingredient: Rice"),
    ],
)
def test_an_unknown_name_is_400_and_writes_nothing(admin, db_session, system_account, overrides, detail):
    db_session.commit()
    before = (_count(db_session, models.Recipe, system_account), _count(db_session, models.Ingredient, system_account),
              _count(db_session, models.Tag, system_account))

    response = admin.post("/admin/catalog/recipes", json=recipe_body(**overrides))

    assert response.status_code == 400
    assert response.json()["detail"] == detail
    db_session.expire_all()
    after = (_count(db_session, models.Recipe, system_account), _count(db_session, models.Ingredient, system_account),
             _count(db_session, models.Tag, system_account))
    assert after == before


def test_a_name_only_the_admin_owns_is_unknown(admin, db_session, admin_user):
    """D3 / ADM-12: the admin's own pantry is never a source of catalog ingredients."""
    crud.get_or_create_ingredient(db_session, None, "Grandma's secret spice", admin_user.id)
    db_session.flush()

    response = admin.post(
        "/admin/catalog/recipes",
        json=recipe_body(ingredients=[{"name": "Grandma's secret spice", "quantity": 1, "unit": "g"}]),
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Unknown ingredient: Grandma's secret spice"


@pytest.mark.parametrize(
    ("overrides", "part"),
    [({"title": "   "}, "title"), ({"ingredients": []}, "ingredients"), ({"procedure": ""}, "procedure")],
)
def test_an_incomplete_published_create_is_400_naming_the_part_and_writes_nothing(
    admin, db_session, system_account, overrides, part
):
    db_session.commit()
    before = _count(db_session, models.Recipe, system_account)

    response = admin.post("/admin/catalog/recipes", json=recipe_body(**overrides))

    assert response.status_code == 400
    assert part in response.json()["detail"]
    db_session.expire_all()
    assert _count(db_session, models.Recipe, system_account) == before


@pytest.mark.parametrize("extra", [{"user_id": 1}, {"visibility": "public"}, {"is_admin": True}])
def test_a_write_body_with_unknown_fields_is_rejected(admin, db_session, system_account, extra):
    before = _count(db_session, models.Recipe, system_account)

    response = admin.post("/admin/catalog/recipes", json={**recipe_body(), **extra})

    assert response.status_code == 422
    assert _count(db_session, models.Recipe, system_account) == before


@pytest.mark.parametrize(
    "overrides",
    [
        {"course": "dessert"},
        {"servings": 0},
        {"ingredients": [{"name": "Rice", "quantity": 1, "unit": "cup"}]},
        {"ingredients": [{"name": "Rice", "quantity": 0, "unit": "g"}]},
        {"ingredients": [{"name": "Rice", "quantity": 1, "unit": "g", "ingredient_id": 3}]},
    ],
)
def test_a_write_body_is_validated(admin, overrides):
    assert admin.post("/admin/catalog/recipes", json=recipe_body(**overrides)).status_code == 422


@pytest.mark.parametrize("course", ["main", "first-course", "side"])
def test_every_app_course_is_accepted(admin, course):
    assert admin.post("/admin/catalog/recipes", json=recipe_body(course=course)).status_code == 201


def test_the_service_flushes_and_never_commits(db_session, system_account, monkeypatch):
    """Routes own the transaction (FC-5)."""
    commits = []
    monkeypatch.setattr(db_session, "commit", lambda: commits.append(True))
    data = recipe_body()

    recipe = catalog.create_catalog_recipe(db_session, data)
    catalog.update_catalog_recipe(db_session, recipe.id, {**data, "title": "Renamed"})

    assert recipe.id is not None and recipe.title == "Renamed"
    assert commits == []


def _as_stored(db_session, recipe_id):
    """The AdminRow for ``recipe_id`` rebuilt from the database, nothing from the session."""
    db_session.expire_all()
    recipe = db_session.get(models.Recipe, recipe_id)
    count = catalog.adoption_counts(db_session, [recipe_id])[recipe_id]
    return catalog_admin_routes.AdminRecipe.build(catalog.CatalogRow(recipe, count)).model_dump(mode="json")


def test_every_write_response_is_the_row_as_committed(admin, db_session, make_catalog_recipe, other_user):
    """A write's body is what a fresh read of the committed rows would render, drafts included."""
    source = make_catalog_recipe("Stored", ingredients=(("Rice", 80, "g"),), tags=("rice",))
    catalog.adopt(db_session, other_user, [source.id])
    draft_id = None
    calls = [
        lambda: admin.post("/admin/catalog/recipes", json=recipe_body()),
        lambda: admin.post("/admin/catalog/recipes", json={**recipe_body(title="Draft"), "publish": False}),
        lambda: admin.put(f"/admin/catalog/recipes/{draft_id}", json=recipe_body(title="Draft, edited")),
        lambda: admin.put(
            f"/admin/catalog/recipes/{source.id}",
            json=recipe_body(ingredients=[{"name": "Onion", "quantity": 1, "unit": "piece"},
                                          {"name": "Rice", "quantity": 90, "unit": "g"}]),
        ),
        lambda: admin.post(f"/admin/catalog/recipes/{source.id}/retire"),
        lambda: admin.post(f"/admin/catalog/recipes/{source.id}/publish"),
        lambda: admin.post(f"/admin/catalog/recipes/{draft_id}/publish"),
    ]

    for call in calls:
        response = call()
        assert response.status_code in (200, 201), response.text
        body = response.json()
        draft_id = draft_id or (body["id"] if body["status"] is None else None)
        assert body == _as_stored(db_session, body["id"])


# --- Admin listing (API-9, RET-4) ---------------------------------------------


def test_the_admin_listing_shows_published_and_retired_with_status_and_counts(
    admin, db_session, other_user, make_catalog_recipe
):
    live = make_catalog_recipe("Live", procedure="Serve.")
    gone = make_catalog_recipe("Gone")
    catalog.adopt(db_session, other_user, [gone.id])
    assert admin.post(f"/admin/catalog/recipes/{gone.id}/retire").status_code == 200

    response = admin.get("/admin/catalog/recipes")

    assert response.status_code == 200
    rows = response.json()
    assert [row["title"] for row in rows] == ["Gone", "Live"]
    assert all(set(row) == ADMIN_ROW_KEYS for row in rows)
    by_title = {row["title"]: row for row in rows}
    assert by_title["Live"]["status"] == "published"
    assert by_title["Live"]["retired_at"] is None
    assert by_title["Live"]["procedure"] == "Serve."
    assert by_title["Gone"]["status"] == "retired"
    assert datetime.fromisoformat(by_title["Gone"]["retired_at"])
    assert by_title["Gone"]["adoption_count"] == 1
    assert by_title["Live"]["id"] == live.id
    assert "mealplanner" not in response.text


# --- Update (API-11) ----------------------------------------------------------


def test_put_replaces_fields_ingredients_and_tags_but_not_adopters_copies(
    admin, db_session, other_user, make_catalog_recipe, system_account
):
    source = make_catalog_recipe(
        "Old title", ingredients=(("Pasta", 80, "g"), ("Tomato", 1, "piece")), tags=("pasta", "vegan")
    )
    [copy_id] = catalog.adopt(db_session, other_user, [source.id]).created_ids

    response = admin.put(f"/admin/catalog/recipes/{source.id}", json=recipe_body(title="New title", servings=4))

    assert response.status_code == 200, response.text
    row = response.json()
    assert set(row) == ADMIN_ROW_KEYS
    assert row["title"] == "New title" and row["servings"] == 4 and row["course"] == "first-course"
    assert _names(row["ingredients"]) == [("Onion", 1, "piece"), ("Rice", 160, "g")]
    assert sorted(row["tags"]) == ["quick", "rice"]
    assert row["status"] == "published" and row["adoption_count"] == 1

    db_session.expire_all()
    stored = db_session.get(models.Recipe, source.id)
    assert sorted(line.ingredient.name for line in stored.ingredients) == ["Onion", "Rice"]
    assert sorted(tag.name for tag in stored.tags) == ["quick", "rice"]
    assert stored.user_id == system_account.id

    copy = db_session.get(models.Recipe, copy_id)
    assert copy.title == "Old title"
    assert sorted(line.ingredient.name for line in copy.ingredients) == ["Pasta", "Tomato"]
    assert sorted(tag.name for tag in copy.tags) == ["pasta", "vegan"]
    assert {line.ingredient.user_id for line in copy.ingredients} == {other_user.id}


def test_put_can_keep_an_ingredient_it_already_had(admin, make_catalog_recipe):
    source = make_catalog_recipe("Same rice", ingredients=(("Rice", 80, "g"),), tags=("rice",))

    response = admin.put(
        f"/admin/catalog/recipes/{source.id}",
        json=recipe_body(ingredients=[{"name": "Rice", "quantity": 90, "unit": "g"}], tags=["rice"]),
    )

    assert response.status_code == 200, response.text
    assert _names(response.json()["ingredients"]) == [("Rice", 90, "g")]


def test_put_on_a_user_owned_or_missing_recipe_is_404(admin, db_session, other_user):
    theirs = crud.create_recipe(db_session, title="Theirs", procedure="Mine.", user_id=other_user.id)

    assert admin.put(f"/admin/catalog/recipes/{theirs.id}", json=recipe_body()).status_code == 404
    assert admin.put(f"/admin/catalog/recipes/{MISSING_ID}", json=recipe_body()).status_code == 404
    db_session.expire_all()
    assert db_session.get(models.Recipe, theirs.id).title == "Theirs"


def test_put_edits_a_draft(admin):
    """Decision: a draft (``publish: false``) is a catalog recipe with no entry yet."""
    draft = admin.post("/admin/catalog/recipes", json={**recipe_body(), "publish": False}).json()

    response = admin.put(f"/admin/catalog/recipes/{draft['id']}", json=recipe_body(title="Better draft"))

    assert response.status_code == 200, response.text
    assert response.json()["title"] == "Better draft"
    assert response.json()["status"] is None


def test_put_cannot_make_a_published_recipe_incomplete(admin, db_session, make_catalog_recipe):
    """CAT-10 holds for a published entry whichever route changes it."""
    source = make_catalog_recipe("Complete", procedure="Cook it.", ingredients=(("Pasta", 80, "g"),))
    db_session.commit()

    response = admin.put(f"/admin/catalog/recipes/{source.id}", json=recipe_body(title="Changed", procedure=" "))

    assert response.status_code == 400
    assert "procedure" in response.json()["detail"]
    db_session.expire_all()
    stored = db_session.get(models.Recipe, source.id)
    assert stored.title == "Complete" and stored.procedure == "Cook it."
    assert [line.ingredient.name for line in stored.ingredients] == ["Pasta"]


def test_put_may_leave_a_retired_recipe_incomplete_until_it_is_republished(admin, make_catalog_recipe):
    source = make_catalog_recipe("Resting", status="retired")

    assert admin.put(f"/admin/catalog/recipes/{source.id}", json=recipe_body(procedure="")).status_code == 200

    response = admin.post(f"/admin/catalog/recipes/{source.id}/publish")
    assert response.status_code == 400
    assert "procedure" in response.json()["detail"]


# --- Publish / retire (API-12, CAT-6..10, ERR-6/7, RET-1, RET-4) -------------


def test_publishing_another_users_recipe_is_403_and_creates_no_entry(admin, db_session, other_user):
    theirs = crud.create_recipe(db_session, title="Theirs", procedure="Mine.", user_id=other_user.id)
    db_session.commit()

    response = admin.post(f"/admin/catalog/recipes/{theirs.id}/publish")

    assert response.status_code == 403
    db_session.expire_all()
    assert db_session.get(models.Recipe, theirs.id).catalog_entry is None


def test_publish_and_retire_of_a_missing_recipe_are_404(admin):
    assert admin.post(f"/admin/catalog/recipes/{MISSING_ID}/publish").status_code == 404
    assert admin.post(f"/admin/catalog/recipes/{MISSING_ID}/retire").status_code == 404


def test_retiring_an_uncatalogued_recipe_is_404(admin, db_session, other_user):
    draft = admin.post("/admin/catalog/recipes", json={**recipe_body(), "publish": False}).json()
    theirs = crud.create_recipe(db_session, title="Theirs", user_id=other_user.id)

    assert admin.post(f"/admin/catalog/recipes/{draft['id']}/retire").status_code == 404
    assert admin.post(f"/admin/catalog/recipes/{theirs.id}/retire").status_code == 404


def test_publishing_a_draft_creates_its_entry(admin):
    draft = admin.post("/admin/catalog/recipes", json={**recipe_body(), "publish": False}).json()

    response = admin.post(f"/admin/catalog/recipes/{draft['id']}/publish")

    assert response.status_code == 200, response.text
    assert set(response.json()) == ADMIN_ROW_KEYS
    assert response.json()["status"] == "published"


def test_publishing_an_incomplete_draft_is_400_naming_the_part(admin):
    draft = admin.post("/admin/catalog/recipes", json={**recipe_body(ingredients=[]), "publish": False})
    assert draft.status_code == 201

    response = admin.post(f"/admin/catalog/recipes/{draft.json()['id']}/publish")

    assert response.status_code == 400
    assert "ingredients" in response.json()["detail"]


def test_publish_retire_republish_over_http(admin, make_catalog_recipe):
    recipe = make_catalog_recipe("Cycle")
    path = f"/admin/catalog/recipes/{recipe.id}"

    first = admin.post(f"{path}/publish").json()
    again = admin.post(f"{path}/publish").json()
    assert first["status"] == again["status"] == "published"
    assert again["published_at"] == first["published_at"]  # CAT-6

    retired = admin.post(f"{path}/retire").json()
    assert retired["status"] == "retired"  # CAT-8
    assert datetime.fromisoformat(retired["retired_at"])
    assert admin.post(f"{path}/retire").json()["retired_at"] == retired["retired_at"]

    back = admin.post(f"{path}/publish").json()
    assert back["status"] == "published" and back["retired_at"] is None  # CAT-7
    assert back["published_at"] == first["published_at"]


def test_a_retired_entry_leaves_the_user_facing_catalog_even_for_the_admin(
    admin, db_session, other_user, make_catalog_recipe
):
    """RET-1, with its count still on the admin listing (RET-4)."""
    recipe = make_catalog_recipe("Vanishing")
    catalog.adopt(db_session, other_user, [recipe.id])
    assert [r["id"] for r in admin.get("/catalog/recipes").json()] == [recipe.id]

    assert admin.post(f"/admin/catalog/recipes/{recipe.id}/retire").status_code == 200

    assert admin.get("/catalog/recipes").json() == []
    assert admin.get(f"/catalog/recipes/{recipe.id}").status_code == 404
    [row] = admin.get("/admin/catalog/recipes").json()
    assert row["id"] == recipe.id and row["status"] == "retired" and row["adoption_count"] == 1


# --- The system vocabulary (D3) ------------------------------------------------


def test_the_ingredients_route_lists_only_the_system_accounts_rows(
    admin, db_session, admin_user, other_user, system_account
):
    crud.get_or_create_ingredient(db_session, None, "Admin-only spice", admin_user.id)
    crud.get_or_create_ingredient(db_session, None, "Other-only spice", other_user.id)
    db_session.flush()

    response = admin.get("/admin/catalog/ingredients")

    assert response.status_code == 200
    rows = response.json()
    assert all(
        set(row) == {"id", "name", "season_months", "grams_per_ml", "grams_per_piece", "preferred_dimension"}
        for row in rows
    )
    names = {row["name"] for row in rows}
    assert "Admin-only spice" not in names and "Other-only spice" not in names
    system_ids = set(db_session.scalars(
        select(models.Ingredient.id).where(models.Ingredient.user_id == system_account.id)
    ))
    assert {row["id"] for row in rows} == system_ids
    tomato = next(row for row in rows if row["name"] == "Tomato")
    assert tomato["season_months"] == [6, 7, 8, 9]
    assert tomato["grams_per_piece"] == 120
    assert tomato["preferred_dimension"] == "mass"


def test_the_tags_route_lists_only_the_system_accounts_rows(
    admin, db_session, admin_user, other_user, system_account
):
    crud.get_or_create_tag(db_session, "admin-only", admin_user.id)
    crud.get_or_create_tag(db_session, "other-only", other_user.id)
    db_session.flush()

    response = admin.get("/admin/catalog/tags")

    assert response.status_code == 200
    rows = response.json()
    assert all(set(row) == {"id", "name"} for row in rows)
    system_ids = set(db_session.scalars(select(models.Tag.id).where(models.Tag.user_id == system_account.id)))
    assert {row["id"] for row in rows} == system_ids
    assert {"admin-only", "other-only"}.isdisjoint(row["name"] for row in rows)
    assert "vegan" in {row["name"] for row in rows}


# --- ADM-9 / ADM-10 and non-admin reach ------------------------------------------


def test_the_admins_own_recipe_book_holds_no_system_recipes(admin, db_session, admin_user, make_catalog_recipe):
    make_catalog_recipe("Catalogued")
    created = admin.post("/admin/catalog/recipes", json=recipe_body()).json()
    mine = crud.create_recipe(db_session, title="My own", user_id=admin_user.id)

    response = admin.get("/recipes")

    assert response.status_code == 200
    assert [row["id"] for row in response.json()] == [mine.id]
    assert admin.get(f"/recipes/{created['id']}").status_code == 404


def test_a_non_admin_cannot_reach_admin_data_through_the_user_catalog(db_session, user, make_catalog_recipe):
    live = make_catalog_recipe("Live", procedure="Secret technique.")
    gone = make_catalog_recipe("Gone", status="retired")
    client = client_as(db_session, user)
    try:
        listing = client.get("/catalog/recipes")
        retired_detail = client.get(f"/catalog/recipes/{gone.id}")
    finally:
        app.dependency_overrides.clear()

    assert [row["id"] for row in listing.json()] == [live.id]
    assert "Secret technique." not in listing.text
    assert all("procedure" not in row and "status" not in row for row in listing.json())
    assert retired_detail.status_code == 404


# --- ADM-11 -----------------------------------------------------------------------


@pytest.mark.parametrize(("method", "path"), WRITE_ROUTES)
def test_admin_write_routes_are_rate_limited(db_session, admin_user, system_account, monkeypatch, method, path):
    import auth_users

    db_session.commit()
    monkeypatch.setattr(app.state.share_limiter, "enabled", True)
    token = auth_users.create_access_token(str(admin_user.id))
    client = client_as(db_session, admin_user)
    # Cheap calls: a missing id (404) or an unknown ingredient (400) still spends
    # the budget, and writes nothing.
    body = recipe_body(ingredients=[{"name": "Unobtainium", "quantity": 1, "unit": "g"}])
    try:
        statuses = []
        for _ in range(500):
            statuses.append(
                client.request(
                    method,
                    _fill(path, MISSING_ID),
                    json=body if method in {"POST", "PUT"} else None,
                    headers={"Authorization": f"Bearer {token}"},
                ).status_code
            )
            if statuses[-1] == 429:
                break
    finally:
        app.dependency_overrides.clear()

    assert statuses[-1] == 429
    assert 429 not in statuses[:-1]


# --- ERR-5 --------------------------------------------------------------------------


@pytest.mark.parametrize(("method", "path"), ROUTER_TABLE)
def test_a_missing_system_account_is_a_named_500(admin, db_session, make_catalog_recipe, caplog, method, path):
    recipe_id = make_catalog_recipe("Orphaned").id
    db_session.execute(update(models.User).where(models.User.is_system.is_(True)).values(is_system=False))
    db_session.expire_all()

    with caplog.at_level(logging.ERROR):
        response = _call(admin, method, path, recipe_id)

    assert response.status_code == 500
    assert "mealplanner" not in response.text
    assert any(
        record.levelno == logging.ERROR and "no is_system account" in record.getMessage()
        for record in caplog.records
    )
