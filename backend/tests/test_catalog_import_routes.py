"""HTTP for the reviewed catalog import (plan phase 3).

The service (`catalog_import`) is tested separately; these tests are about the
router: the exact route table, the guards every route sits behind, the status
codes the service's exceptions map onto, and that writes commit.

Like ``tests/test_catalog_admin.py``, every test builds on ``system_account``,
which empties the catalog inside the test's transaction.
"""

import logging

import pytest
from sqlalchemy import select, update

import catalog_import_routes
import models
from main import app
from tests.conftest import client_as, db_client

MISSING_ID = 10**9

#: The route table this router serves, exactly.
#:
#: Mounted under ``/admin/catalog/imports``, as the plan specified. The
#: no-DELETE contract in ``tests/test_catalog_admin.py`` (API-14, RET-5) covers
#: ``/admin/catalog/recipes`` only, so abandoning a batch may be a DELETE here.
CONTRACT_ROUTES = {
    ("GET", "/admin/catalog/imports"),
    ("POST", "/admin/catalog/imports"),
    ("GET", "/admin/catalog/imports/{batch_id}"),
    ("DELETE", "/admin/catalog/imports/{batch_id}"),
    ("GET", "/admin/catalog/imports/{batch_id}/items/{item_id}"),
    ("PATCH", "/admin/catalog/imports/{batch_id}/items/{item_id}"),
    ("POST", "/admin/catalog/imports/{batch_id}/items/{item_id}/skip"),
    ("POST", "/admin/catalog/imports/{batch_id}/items/{item_id}/commit"),
}
WRITE_METHODS = {"POST", "PATCH", "DELETE"}
WRITE_ROUTES = sorted((m, p) for m, p in CONTRACT_ROUTES if m in WRITE_METHODS)


def _router_table():
    return sorted(
        (method, route.path)
        for route in catalog_import_routes.router.routes
        for method in route.methods
    )


ROUTER_TABLE = _router_table()

BATCH_KEYS = {"id", "filename", "created_at", "created_by_user_id", "counts", "items"}
ITEM_KEYS = {
    "id", "position", "title", "state", "error",
    "problems", "duplicate_recipe_id", "committed_recipe_id",
}
DETAIL_KEYS = ITEM_KEYS | {"source", "draft", "duplicate"}


def entry(**overrides):
    body = {
        "title": "Imported risotto",
        "course": "first-course",
        "servings": 2,
        "bulk_prep": True,
        "procedure": "Toast the rice.",
        "image_url": None,
        "tags": ["rice"],
        "ingredients": [{"name": "Rice", "quantity": 160, "unit": "g"}],
    }
    body.update(overrides)
    return body


def upload_body(entries=None, filename="pack.json"):
    return {"filename": filename, "entries": entries if entries is not None else [entry()]}


def _fill(path, batch_id, item_id):
    return path.replace("{batch_id}", str(batch_id)).replace("{item_id}", str(item_id))


def _call(client, method, path, batch_id=MISSING_ID, item_id=MISSING_ID):
    body = None
    if method == "POST" and path.endswith("imports"):
        body = upload_body()
    elif method == "PATCH":
        body = {"draft": entry()}
    return client.request(method, _fill(path, batch_id, item_id), json=body)


@pytest.fixture
def admin(db_session, admin_user, system_account):
    try:
        yield client_as(db_session, admin_user)
    finally:
        app.dependency_overrides.clear()


# --- route table and guards ---------------------------------------------------


def test_the_router_serves_exactly_the_contract_routes():
    assert set(ROUTER_TABLE) == CONTRACT_ROUTES


def test_the_router_is_mounted_on_the_app():
    mounted = {
        (method, route.path)
        for route in app.routes
        for method in (getattr(route, "methods", None) or set())
    }
    assert CONTRACT_ROUTES <= mounted


def test_every_route_depends_on_require_admin_and_the_catalog():
    import auth_users
    import catalog_admin_routes

    deps = [dep.dependency for dep in catalog_import_routes.router.dependencies]
    assert auth_users.require_admin in deps
    assert catalog_admin_routes._require_catalog in deps


@pytest.mark.parametrize(("method", "path"), ROUTER_TABLE)
def test_every_route_is_401_for_anonymous_callers(db_session, method, path):
    try:
        response = _call(db_client(db_session), method, path)
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 401


@pytest.mark.parametrize(("method", "path"), ROUTER_TABLE)
def test_every_route_is_one_identical_403_for_a_non_admin(db_session, user, system_account, method, path):
    client = client_as(db_session, user)
    try:
        first = _call(client, method, path)
        second = _call(client, method, path, batch_id=1, item_id=1)
    finally:
        app.dependency_overrides.clear()

    assert first.status_code == second.status_code == 403
    assert first.json() == {"detail": "Forbidden"}
    assert first.content == second.content


@pytest.mark.parametrize(("method", "path"), ROUTER_TABLE)
def test_a_missing_system_account_is_a_named_500(admin, db_session, caplog, method, path):
    db_session.execute(update(models.User).where(models.User.is_system.is_(True)).values(is_system=False))
    db_session.expire_all()

    with caplog.at_level(logging.ERROR):
        response = _call(admin, method, path)

    assert response.status_code == 500
    assert "mealplanner" not in response.text


@pytest.mark.parametrize(("method", "path"), WRITE_ROUTES)
def test_write_routes_are_rate_limited(db_session, admin_user, system_account, monkeypatch, method, path):
    import auth_users

    db_session.commit()
    monkeypatch.setattr(app.state.share_limiter, "enabled", True)
    token = auth_users.create_access_token(str(admin_user.id))
    client = client_as(db_session, admin_user)
    try:
        statuses = []
        for _ in range(500):
            response = client.request(
                method,
                _fill(path, MISSING_ID, MISSING_ID),
                json={"draft": entry()} if method == "PATCH" else (
                    upload_body(entries=[]) if path.endswith("imports") else None
                ),
                headers={"Authorization": f"Bearer {token}"},
            )
            statuses.append(response.status_code)
            if statuses[-1] == 429:
                break
    finally:
        app.dependency_overrides.clear()

    assert statuses[-1] == 429
    assert 429 not in statuses[:-1]


# --- upload -------------------------------------------------------------------


def test_upload_stages_the_file_and_commits_it(admin, db_session):
    response = admin.post("/admin/catalog/imports", json=upload_body())

    assert response.status_code == 201, response.text
    body = response.json()
    assert set(body) == BATCH_KEYS
    assert body["filename"] == "pack.json"
    assert body["counts"] == {"pending": 1, "invalid": 0, "skipped": 0, "committed": 0}
    assert len(body["items"]) == 1
    item = body["items"][0]
    assert set(item) == ITEM_KEYS
    assert item["title"] == "Imported risotto"
    assert item["state"] == "pending"
    # "Rice" and "rice" are seeded system vocabulary, so this entry resolves.
    assert item["problems"] == []

    db_session.expire_all()
    assert db_session.get(models.CatalogImportBatch, body["id"]) is not None


def test_a_malformed_entry_is_staged_invalid_rather_than_rejecting_the_file(admin):
    response = admin.post(
        "/admin/catalog/imports",
        json=upload_body(entries=[entry(), entry(title="", course="main")]),
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["counts"]["invalid"] == 1
    bad = body["items"][1]
    assert bad["state"] == "invalid"
    assert bad["error"] == "title is required"


def test_upload_flags_a_duplicate_title(admin, make_catalog_recipe):
    existing = make_catalog_recipe("Imported risotto")

    body = admin.post("/admin/catalog/imports", json=upload_body()).json()

    assert body["items"][0]["duplicate_recipe_id"] == existing.id


def test_upload_refuses_an_unknown_field(admin):
    response = admin.post("/admin/catalog/imports", json={**upload_body(), "publish": True})

    assert response.status_code == 422


# --- listing ------------------------------------------------------------------


def test_the_listing_is_null_with_no_open_batch(admin):
    response = admin.get("/admin/catalog/imports")

    assert response.status_code == 200
    assert response.json() is None


def test_the_listing_is_the_open_batch(admin):
    created = admin.post("/admin/catalog/imports", json=upload_body()).json()

    body = admin.get("/admin/catalog/imports").json()

    assert body["id"] == created["id"]
    assert set(body) == BATCH_KEYS


def test_a_missing_batch_is_404(admin):
    assert admin.get(f"/admin/catalog/imports/{MISSING_ID}").status_code == 404


# --- one item -----------------------------------------------------------------


def test_item_detail_carries_the_draft_the_source_and_the_duplicate(admin, make_catalog_recipe):
    existing = make_catalog_recipe("Imported risotto")
    batch = admin.post("/admin/catalog/imports", json=upload_body()).json()
    item_id = batch["items"][0]["id"]

    response = admin.get(f"/admin/catalog/imports/{batch['id']}/items/{item_id}")

    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == DETAIL_KEYS
    assert body["source"]["title"] == "Imported risotto"
    assert body["draft"]["ingredients"][0]["ingredient_id"] is not None
    assert body["duplicate"]["id"] == existing.id
    assert body["duplicate"]["title"] == "Imported risotto"


def test_item_detail_has_no_duplicate_when_nothing_collides(admin):
    batch = admin.post("/admin/catalog/imports", json=upload_body()).json()
    item_id = batch["items"][0]["id"]

    body = admin.get(f"/admin/catalog/imports/{batch['id']}/items/{item_id}").json()

    assert body["duplicate"] is None


def test_an_item_of_another_batch_is_404(admin):
    first = admin.post("/admin/catalog/imports", json=upload_body()).json()
    second = admin.post("/admin/catalog/imports", json=upload_body()).json()

    response = admin.get(f"/admin/catalog/imports/{second['id']}/items/{first['items'][0]['id']}")

    assert response.status_code == 404


def test_a_missing_item_is_404(admin):
    batch = admin.post("/admin/catalog/imports", json=upload_body()).json()

    assert admin.get(f"/admin/catalog/imports/{batch['id']}/items/{MISSING_ID}").status_code == 404


# --- editing ------------------------------------------------------------------


def test_patch_saves_the_working_copy_and_leaves_the_source_alone(admin, db_session):
    batch = admin.post("/admin/catalog/imports", json=upload_body()).json()
    item_id = batch["items"][0]["id"]

    response = admin.patch(
        f"/admin/catalog/imports/{batch['id']}/items/{item_id}",
        json={"draft": entry(title="Corrected risotto")},
    )

    assert response.status_code == 200, response.text
    assert response.json()["draft"]["title"] == "Corrected risotto"
    assert response.json()["source"]["title"] == "Imported risotto"
    db_session.expire_all()
    stored = db_session.get(models.CatalogImportItem, item_id)
    assert stored.draft["title"] == "Corrected risotto"
    assert stored.source["title"] == "Imported risotto"


def test_patching_an_entry_into_shape_clears_invalid(admin):
    batch = admin.post(
        "/admin/catalog/imports", json=upload_body(entries=[entry(title="")])
    ).json()
    item_id = batch["items"][0]["id"]

    body = admin.patch(
        f"/admin/catalog/imports/{batch['id']}/items/{item_id}", json={"draft": entry()}
    ).json()

    assert body["state"] == "pending"
    assert body["error"] is None


def test_patching_out_of_shape_is_invalid_not_a_400(admin):
    batch = admin.post("/admin/catalog/imports", json=upload_body()).json()
    item_id = batch["items"][0]["id"]

    body = admin.patch(
        f"/admin/catalog/imports/{batch['id']}/items/{item_id}",
        json={"draft": entry(servings=0)},
    ).json()

    assert body["state"] == "invalid"
    assert body["error"] == "servings must be greater than or equal to 1"


# --- skip and commit ----------------------------------------------------------


def test_skip_marks_the_item_and_prunes_the_finished_batch(admin, db_session):
    batch = admin.post("/admin/catalog/imports", json=upload_body()).json()
    item_id = batch["items"][0]["id"]

    response = admin.post(f"/admin/catalog/imports/{batch['id']}/items/{item_id}/skip")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["item"]["state"] == "skipped"
    assert body["batch_deleted"] is True
    db_session.expire_all()
    assert db_session.get(models.CatalogImportBatch, batch["id"]) is None


def test_skip_keeps_a_batch_with_work_left(admin, db_session):
    batch = admin.post("/admin/catalog/imports", json=upload_body(entries=[entry(), entry(title="Other")])).json()

    body = admin.post(
        f"/admin/catalog/imports/{batch['id']}/items/{batch['items'][0]['id']}/skip"
    ).json()

    assert body["batch_deleted"] is False
    db_session.expire_all()
    assert db_session.get(models.CatalogImportBatch, batch["id"]) is not None


def test_commit_creates_a_draft_recipe_and_commits(admin, db_session, system_account):
    db_session.commit()
    batch = admin.post("/admin/catalog/imports", json=upload_body(entries=[entry(), entry(title="Other")])).json()
    item_id = batch["items"][0]["id"]

    response = admin.post(f"/admin/catalog/imports/{batch['id']}/items/{item_id}/commit")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["item"]["state"] == "committed"
    assert body["batch_deleted"] is False
    recipe_id = body["item"]["committed_recipe_id"]
    assert recipe_id is not None

    db_session.expire_all()
    recipe = db_session.get(models.Recipe, recipe_id)
    assert recipe.user_id == system_account.id
    assert recipe.catalog_entry is None  # a draft, not a published entry
    assert db_session.get(models.CatalogImportItem, item_id).state == "committed"


def test_committing_an_unresolved_item_is_400_and_writes_nothing(admin, db_session, system_account):
    db_session.commit()
    unknown = entry(ingredients=[{"name": "Unobtainium", "quantity": 1, "unit": "g"}])
    batch = admin.post("/admin/catalog/imports", json=upload_body(entries=[unknown])).json()
    item_id = batch["items"][0]["id"]
    before = db_session.scalar(
        select(models.Recipe.id).where(models.Recipe.user_id == system_account.id).limit(1)
    )

    response = admin.post(f"/admin/catalog/imports/{batch['id']}/items/{item_id}/commit")

    assert response.status_code == 400
    assert "Unknown ingredient: Unobtainium" in response.json()["detail"]
    db_session.expire_all()
    after = db_session.scalar(
        select(models.Recipe.id).where(models.Recipe.user_id == system_account.id).limit(1)
    )
    assert after == before
    assert db_session.get(models.CatalogImportItem, item_id).state == "pending"


def test_committing_twice_is_400(admin, db_session):
    db_session.commit()
    batch = admin.post("/admin/catalog/imports", json=upload_body(entries=[entry(), entry(title="Other")])).json()
    item_id = batch["items"][0]["id"]
    admin.post(f"/admin/catalog/imports/{batch['id']}/items/{item_id}/commit")

    response = admin.post(f"/admin/catalog/imports/{batch['id']}/items/{item_id}/commit")

    assert response.status_code == 400


def test_skip_and_commit_404_on_an_item_of_another_batch(admin):
    first = admin.post("/admin/catalog/imports", json=upload_body()).json()
    second = admin.post("/admin/catalog/imports", json=upload_body()).json()
    item_id = first["items"][0]["id"]

    assert admin.post(f"/admin/catalog/imports/{second['id']}/items/{item_id}/skip").status_code == 404
    assert admin.post(f"/admin/catalog/imports/{second['id']}/items/{item_id}/commit").status_code == 404


# --- abandon ------------------------------------------------------------------


def test_delete_abandons_the_batch(admin, db_session):
    batch = admin.post("/admin/catalog/imports", json=upload_body()).json()

    response = admin.delete(f"/admin/catalog/imports/{batch['id']}")

    assert response.status_code == 204
    db_session.expire_all()
    assert db_session.get(models.CatalogImportBatch, batch["id"]) is None
    assert db_session.get(models.CatalogImportItem, batch["items"][0]["id"]) is None


def test_deleting_a_missing_batch_is_404(admin):
    assert admin.delete(f"/admin/catalog/imports/{MISSING_ID}").status_code == 404
