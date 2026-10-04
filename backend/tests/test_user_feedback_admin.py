"""Admin feedback triage routes (``/admin/feedback/*``).

Items are filed through :func:`user_feedback.submit`, the same path the user
route takes, so every assertion is about rows built the production way. The
shared ``db_session`` scopes each service commit to a SAVEPOINT, so a test can
commit freely and the outer transaction still discards everything.
"""

import pytest

import auth_users
import models
import storage
import user_feedback
import user_feedback_admin_routes
from main import app
from tests.conftest import client_as, db_client

MISSING_ID = 10**9
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16

ITEM_KEYS = {
    "id", "ref_code", "title", "body", "type", "status", "priority", "seen",
    "page_path", "user_agent", "viewport_width", "has_screenshot", "admin_notes",
    "tags", "author", "created_at", "updated_at",
}
AUTHOR_KEYS = {"id", "email", "username", "display_name"}

#: The HTTP contract's admin route table, exactly.
CONTRACT_ROUTES = frozenset({
    ("GET", "/admin/feedback"),
    ("GET", "/admin/feedback/unseen-count"),
    ("GET", "/admin/feedback/tags"),
    ("PATCH", "/admin/feedback/tags/{tag_id}"),
    ("GET", "/admin/feedback/{item_id}"),
    ("PATCH", "/admin/feedback/{item_id}"),
    ("GET", "/admin/feedback/{item_id}/screenshot"),
})


def _router_table():
    """Every ``(method, path)`` the admin feedback router actually serves."""
    return sorted(
        (method, route.path)
        for route in user_feedback_admin_routes.router.routes
        for method in route.methods
    )


ROUTER_TABLE = _router_table()


@pytest.fixture
def media(monkeypatch, tmp_path):
    """Local-disk storage under ``tmp_path``, as ``test_recipe_image_upload`` does."""
    monkeypatch.delenv("AWS_S3_BUCKET_NAME", raising=False)
    monkeypatch.setattr(storage, "MEDIA_DIR", tmp_path)
    return tmp_path


@pytest.fixture
def admin(db_session, admin_user):
    try:
        yield client_as(db_session, admin_user)
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def make_item(db_session, user):
    def _make(title="Something broke", type="issue", author=user, **kwargs):
        return user_feedback.submit(db_session, author, title, "It does not work.", type, **kwargs)

    return _make


def _ids(response):
    assert response.status_code == 200, response.text
    return [row["id"] for row in response.json()]


# --- Route table and guard ----------------------------------------------------


def test_the_router_serves_exactly_the_contract_routes():
    assert set(ROUTER_TABLE) == CONTRACT_ROUTES


def test_every_route_depends_on_require_admin():
    assert any(
        dep.dependency is auth_users.require_admin
        for dep in user_feedback_admin_routes.router.dependencies
    )


def _call(client, method, path, item_id, tag_id):
    url = path.replace("{item_id}", str(item_id)).replace("{tag_id}", str(tag_id))
    body = None
    if method == "PATCH":
        body = {"name": "sweep"} if "/tags/" in path else {"status": "in_progress"}
    return client.request(method, url, json=body)


@pytest.mark.parametrize(("method", "path"), ROUTER_TABLE)
def test_every_route_is_401_for_anonymous_callers(db_session, make_item, method, path):
    item = user_feedback.set_tags(db_session, make_item(), ["guarded"])
    try:
        response = _call(db_client(db_session), method, path, item.id, item.tags[0].id)
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 401


@pytest.mark.parametrize(("method", "path"), ROUTER_TABLE)
def test_every_route_is_one_identical_403_for_a_non_admin(db_session, user, media, make_item, method, path):
    """The same bytes whether the id exists or not -- the screenshot stream included."""
    item = make_item(screenshot=(PNG, "image/png"))
    item = user_feedback.set_tags(db_session, item, ["guarded"])
    client = client_as(db_session, user)
    try:
        existing = _call(client, method, path, item.id, item.tags[0].id)
        missing = _call(client, method, path, MISSING_ID, MISSING_ID)
    finally:
        app.dependency_overrides.clear()

    assert existing.status_code == missing.status_code == 403
    assert existing.json() == {"detail": "Forbidden"}
    assert existing.content == missing.content
    assert existing.headers.get("content-type") == missing.headers.get("content-type")
    # Nothing was written by the refused PATCHes.
    db_session.expire_all()
    assert user_feedback.get_item(db_session, item.id).status == "open"
    assert [tag.name for tag in user_feedback.list_tags(db_session)] == ["guarded"]


# --- Serialisation --------------------------------------------------------------


def test_an_item_is_serialised_from_the_allowlist(admin, make_item, media, user):
    item = make_item(
        page_path="/plan", user_agent="UA/1", viewport_width=390, screenshot=(PNG, "image/png")
    )

    row = admin.get(f"/admin/feedback/{item.id}").json()

    assert set(row) == ITEM_KEYS
    assert row["ref_code"] == f"FB-{item.id}"
    assert row["type"] == "issue" and row["status"] == "open" and row["priority"] == "normal"
    assert row["seen"] is False
    assert (row["page_path"], row["user_agent"], row["viewport_width"]) == ("/plan", "UA/1", 390)
    assert row["has_screenshot"] is True
    assert row["admin_notes"] is None and row["tags"] == []
    assert row["author"] == {
        "id": user.id, "email": user.email, "username": user.username, "display_name": user.display_name,
    }
    assert set(row["author"]) == AUTHOR_KEYS


def test_screenshot_key_appears_in_no_response(admin, db_session, make_item, media):
    item = make_item(screenshot=(PNG, "image/png"))
    key = item.screenshot_key
    assert key

    responses = [
        admin.get("/admin/feedback"),
        admin.get(f"/admin/feedback/{item.id}"),
        admin.patch(f"/admin/feedback/{item.id}", json={"tags": ["mobile"], "admin_notes": "n"}),
        admin.get("/admin/feedback/tags"),
        admin.get("/admin/feedback/unseen-count"),
    ]
    for response in responses:
        assert response.status_code == 200, response.text
        assert "screenshot_key" not in response.text
        assert key not in response.text


def test_has_screenshot_is_false_without_one(admin, make_item):
    item = make_item()

    assert admin.get(f"/admin/feedback/{item.id}").json()["has_screenshot"] is False


def test_tags_are_serialised_as_sorted_names(admin, db_session, make_item):
    item = user_feedback.set_tags(db_session, make_item(), ["Zeta", "alpha", "Mobile UI"])

    assert admin.get(f"/admin/feedback/{item.id}").json()["tags"] == ["alpha", "mobile ui", "zeta"]


def test_author_is_null_once_the_filing_account_is_deleted(admin, db_session, make_item, other_user):
    item = make_item(author=other_user)
    db_session.delete(other_user)
    db_session.commit()
    db_session.expire_all()

    row = admin.get(f"/admin/feedback/{item.id}").json()

    assert row["author"] is None
    assert row["title"] == "Something broke"


# --- List -----------------------------------------------------------------------


def test_list_is_newest_first(admin, make_item):
    first, second, third = make_item("a"), make_item("b"), make_item("c")

    assert _ids(admin.get("/admin/feedback")) == [third.id, second.id, first.id]


def test_list_filters_by_status_type_priority_and_seen(admin, db_session, make_item):
    issue = make_item("issue", type="issue")
    request = make_item("request", type="request")
    user_feedback.set_status(db_session, request, "in_progress")
    user_feedback.set_priority(db_session, issue, "high")
    user_feedback.mark_seen(db_session, issue)

    assert _ids(admin.get("/admin/feedback", params={"status": "in_progress"})) == [request.id]
    assert _ids(admin.get("/admin/feedback", params={"type": "issue"})) == [issue.id]
    assert _ids(admin.get("/admin/feedback", params={"priority": "high"})) == [issue.id]
    assert _ids(admin.get("/admin/feedback", params={"seen": "false"})) == [request.id]
    assert _ids(admin.get("/admin/feedback", params={"seen": "true"})) == [issue.id]


def test_list_filters_compose(admin, db_session, make_item):
    match = make_item("match", type="issue")
    wrong_status = make_item("wrong status", type="issue")
    wrong_type = make_item("wrong type", type="request")
    user_feedback.set_priority(db_session, match, "high")
    user_feedback.set_priority(db_session, wrong_type, "high")
    user_feedback.set_priority(db_session, wrong_status, "high")
    user_feedback.set_status(db_session, wrong_status, "closed_fixed")

    response = admin.get("/admin/feedback", params={"type": "issue", "priority": "high", "status": "open"})

    assert _ids(response) == [match.id]


def test_list_tag_filter_ignores_case_and_padding(admin, db_session, make_item):
    tagged = user_feedback.set_tags(db_session, make_item("tagged"), ["mobile"])
    make_item("untagged")

    assert _ids(admin.get("/admin/feedback", params={"tag": "  Mobile "})) == [tagged.id]


@pytest.mark.parametrize("param", ["status", "type", "priority"])
def test_list_rejects_an_unknown_enum_filter(admin, param):
    assert admin.get("/admin/feedback", params={param: "bogus"}).status_code == 422


# --- Detail ---------------------------------------------------------------------


def test_detail_is_404_for_an_unknown_item(admin):
    assert admin.get(f"/admin/feedback/{MISSING_ID}").status_code == 404


def test_detail_does_not_mark_the_item_seen(admin, db_session, make_item):
    """The page marks a row seen with an explicit PATCH; a GET is a pure read."""
    item = make_item()

    admin.get(f"/admin/feedback/{item.id}")

    db_session.expire_all()
    assert user_feedback.get_item(db_session, item.id).seen is False


# --- PATCH ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("change", "field", "expected"),
    [
        ({"status": "closed_fixed"}, "status", "closed_fixed"),
        ({"priority": "low"}, "priority", "low"),
        ({"admin_notes": "  call back  "}, "admin_notes", "call back"),
        ({"tags": ["b", "a"]}, "tags", ["a", "b"]),
        ({"seen": True}, "seen", True),
    ],
)
def test_patch_sets_each_field_and_returns_the_updated_item(admin, db_session, make_item, change, field, expected):
    item = make_item()

    response = admin.patch(f"/admin/feedback/{item.id}", json=change)

    assert response.status_code == 200, response.text
    assert set(response.json()) == ITEM_KEYS
    assert response.json()[field] == expected
    assert admin.get(f"/admin/feedback/{item.id}").json()[field] == expected


def test_patch_several_fields_at_once(admin, make_item):
    item = make_item()

    row = admin.patch(
        f"/admin/feedback/{item.id}",
        json={"status": "in_progress", "priority": "high", "admin_notes": "n", "tags": ["x"], "seen": True},
    ).json()

    assert (row["status"], row["priority"], row["admin_notes"], row["tags"], row["seen"]) == (
        "in_progress", "high", "n", ["x"], True,
    )


def test_patch_admin_notes_null_clears_but_omitted_keeps(admin, db_session, make_item):
    item = user_feedback.set_notes(db_session, make_item(), "keep me")

    kept = admin.patch(f"/admin/feedback/{item.id}", json={"priority": "high"}).json()
    cleared = admin.patch(f"/admin/feedback/{item.id}", json={"admin_notes": None}).json()

    assert kept["admin_notes"] == "keep me"
    assert cleared["admin_notes"] is None


def test_patch_an_empty_body_is_a_no_op(admin, make_item):
    item = make_item()
    before = admin.get(f"/admin/feedback/{item.id}").json()

    response = admin.patch(f"/admin/feedback/{item.id}", json={})

    assert response.status_code == 200
    assert response.json() == before


def test_patch_rejects_an_unknown_key(admin, make_item):
    item = make_item()

    response = admin.patch(f"/admin/feedback/{item.id}", json={"screenshot_key": "x"})

    assert response.status_code == 422


@pytest.mark.parametrize(
    "body",
    [
        {"priority": "high", "status": "bogus"},
        {"priority": "high", "status": None},
        {"seen": True, "priority": "urgent"},
    ],
)
def test_patch_with_an_invalid_value_is_422_and_changes_nothing(admin, db_session, make_item, body):
    item = make_item()

    response = admin.patch(f"/admin/feedback/{item.id}", json=body)

    assert response.status_code == 422
    db_session.expire_all()
    stored = user_feedback.get_item(db_session, item.id)
    assert (stored.status, stored.priority, stored.seen) == ("open", "normal", False)


def test_patch_is_404_for_an_unknown_item(admin):
    assert admin.patch(f"/admin/feedback/{MISSING_ID}", json={"seen": True}).status_code == 404


def test_seen_and_status_move_independently(admin, make_item):
    item = make_item()

    closed = admin.patch(f"/admin/feedback/{item.id}", json={"status": "closed_ignored"}).json()
    read = admin.patch(f"/admin/feedback/{item.id}", json={"seen": True}).json()
    unread = admin.patch(f"/admin/feedback/{item.id}", json={"seen": False}).json()

    assert (closed["status"], closed["seen"]) == ("closed_ignored", False)
    assert (read["status"], read["seen"]) == ("closed_ignored", True)
    assert (unread["status"], unread["seen"]) == ("closed_ignored", False)


# --- Tags -----------------------------------------------------------------------


def test_patch_tags_creates_tags_inline_and_reuses_them_across_case_and_padding(admin, make_item):
    first, second = make_item("a"), make_item("b")

    admin.patch(f"/admin/feedback/{first.id}", json={"tags": ["Mobile"]})
    row = admin.patch(f"/admin/feedback/{second.id}", json={"tags": ["mobile ", "Shopping  List"]}).json()

    assert row["tags"] == ["mobile", "shopping list"]
    tags = admin.get("/admin/feedback/tags").json()
    assert [tag["name"] for tag in tags] == ["mobile", "shopping list"]
    assert all(set(tag) == {"id", "name"} for tag in tags)


def test_patch_tags_replaces_the_whole_set(admin, make_item):
    item = make_item()
    admin.patch(f"/admin/feedback/{item.id}", json={"tags": ["a", "b"]})

    assert admin.patch(f"/admin/feedback/{item.id}", json={"tags": ["c"]}).json()["tags"] == ["c"]
    assert admin.patch(f"/admin/feedback/{item.id}", json={"tags": []}).json()["tags"] == []


def test_list_tags_is_sorted_by_name(admin, db_session, make_item):
    user_feedback.set_tags(db_session, make_item(), ["zeta", "alpha"])

    assert [tag["name"] for tag in admin.get("/admin/feedback/tags").json()] == ["alpha", "zeta"]


def test_rename_tag_normalizes_and_follows_through_to_items(admin, db_session, make_item):
    item = user_feedback.set_tags(db_session, make_item(), ["mobil"])
    tag_id = item.tags[0].id

    response = admin.patch(f"/admin/feedback/tags/{tag_id}", json={"name": "  Mobile  UI "})

    assert response.status_code == 200, response.text
    assert response.json() == {"id": tag_id, "name": "mobile ui"}
    assert admin.get(f"/admin/feedback/{item.id}").json()["tags"] == ["mobile ui"]
    assert _ids(admin.get("/admin/feedback", params={"tag": "Mobile UI"})) == [item.id]


def test_rename_tag_to_a_taken_name_is_409(admin, db_session, make_item):
    item = user_feedback.set_tags(db_session, make_item(), ["mobile", "desktop"])
    desktop = next(tag for tag in item.tags if tag.name == "desktop")

    response = admin.patch(f"/admin/feedback/tags/{desktop.id}", json={"name": "Mobile"})

    assert response.status_code == 409
    db_session.expire_all()
    assert user_feedback.get_tag(db_session, desktop.id).name == "desktop"


def test_rename_unknown_tag_is_404(admin):
    assert admin.patch(f"/admin/feedback/tags/{MISSING_ID}", json={"name": "x"}).status_code == 404


@pytest.mark.parametrize("body", [{"name": "   "}, {"name": ""}, {}, {"name": "x", "extra": 1}])
def test_rename_tag_rejects_a_blank_or_malformed_body(admin, db_session, make_item, body):
    item = user_feedback.set_tags(db_session, make_item(), ["mobile"])

    assert admin.patch(f"/admin/feedback/tags/{item.tags[0].id}", json=body).status_code == 422


# --- Screenshot -----------------------------------------------------------------


def test_screenshot_streams_the_stored_bytes(admin, make_item, media):
    item = make_item(screenshot=(PNG, "image/png"))

    response = admin.get(f"/admin/feedback/{item.id}/screenshot")

    assert response.status_code == 200
    assert response.content == PNG
    assert response.headers["content-type"] == "image/png"
    assert response.headers["cache-control"] == "private, no-store"


def test_screenshot_is_404_without_one(admin, make_item):
    item = make_item()

    assert admin.get(f"/admin/feedback/{item.id}/screenshot").status_code == 404


def test_screenshot_is_404_for_an_unknown_item(admin):
    assert admin.get(f"/admin/feedback/{MISSING_ID}/screenshot").status_code == 404


def test_screenshot_is_404_when_the_stored_object_is_missing(admin, make_item, media):
    item = make_item(screenshot=(PNG, "image/png"))
    (media / item.screenshot_key).unlink()

    assert admin.get(f"/admin/feedback/{item.id}/screenshot").status_code == 404


# --- Unseen count ---------------------------------------------------------------


def test_unseen_count_matches_the_rows(admin, db_session, make_item):
    items = [make_item(str(n)) for n in range(3)]
    user_feedback.mark_seen(db_session, items[0])

    response = admin.get("/admin/feedback/unseen-count")

    assert response.status_code == 200
    assert response.json() == {"count": 2}
    assert response.json()["count"] == len(admin.get("/admin/feedback", params={"seen": "false"}).json())


# --- Rate limiting --------------------------------------------------------------


@pytest.mark.parametrize("path", ["/admin/feedback/{MISSING_ID}", "/admin/feedback/tags/{MISSING_ID}"])
def test_write_routes_are_rate_limited(db_session, admin_user, monkeypatch, path):
    db_session.commit()
    monkeypatch.setattr(app.state.share_limiter, "enabled", True)
    token = auth_users.create_access_token(str(admin_user.id))
    client = client_as(db_session, admin_user)
    body = {"name": "probe"} if "/tags/" in path else {"seen": True}
    url = path.replace("{MISSING_ID}", str(MISSING_ID))
    try:
        statuses = []
        for _ in range(500):
            statuses.append(
                client.patch(url, json=body, headers={"Authorization": f"Bearer {token}"}).status_code
            )
            if statuses[-1] == 429:
                break
    finally:
        app.dependency_overrides.clear()

    assert statuses[-1] == 429


def test_models_value_tuples_are_what_the_router_validates_against():
    """The Literal types are spelled from the models' tuples, not copied."""
    assert user_feedback_admin_routes.STATUS.__args__ == models.FEEDBACK_STATUS_VALUES
    assert user_feedback_admin_routes.PRIORITY.__args__ == models.FEEDBACK_PRIORITY_VALUES
    assert user_feedback_admin_routes.TYPE.__args__ == models.FEEDBACK_TYPE_VALUES
