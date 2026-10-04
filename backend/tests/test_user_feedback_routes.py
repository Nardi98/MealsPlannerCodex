"""``POST /feedback``: the one route through which a user files feedback.

Multipart, like the recipe image upload, because of the optional screenshot.
Storage runs in local-fallback mode against ``tmp_path``.
"""
import pytest

import models
import ratelimit
import storage
from conftest import client_as
from main import app

VALID = {"title": "Shopping list is empty", "body": "Nothing shows after I plan.", "type": "issue"}


@pytest.fixture(autouse=True)
def local_media(tmp_path, monkeypatch):
    monkeypatch.delenv("AWS_S3_BUCKET_NAME", raising=False)
    monkeypatch.setattr(storage, "MEDIA_DIR", tmp_path)


@pytest.fixture
def client(db_session, user):
    try:
        yield client_as(db_session, user)
    finally:
        app.dependency_overrides.clear()


def _items(db_session):
    return db_session.query(models.FeedbackItem).all()


def test_submit_returns_201_and_only_the_ref_code_of_the_stored_row(client, db_session):
    response = client.post("/feedback", data=VALID)

    assert response.status_code == 201
    [item] = _items(db_session)
    assert response.json() == {"ref_code": f"FB-{item.id}"}
    assert item.ref_code == f"FB-{item.id}"
    assert (item.title, item.body, item.type) == (VALID["title"], VALID["body"], "issue")


def test_the_response_leaks_no_admin_fields(client):
    response = client.post("/feedback", data=VALID, files={"screenshot": ("s.png", b"png", "image/png")})

    assert response.status_code == 201
    assert "admin_notes" not in response.text
    assert "screenshot_key" not in response.text


def test_the_item_is_attributed_to_the_caller(client, db_session, user):
    client.post("/feedback", data=VALID)

    [item] = _items(db_session)
    assert item.user_id == user.id


def test_client_context_is_stored(client, db_session):
    response = client.post(
        "/feedback",
        data={**VALID, "page_path": "/plan", "user_agent": "Mozilla/5.0", "viewport_width": "390"},
    )

    assert response.status_code == 201
    [item] = _items(db_session)
    assert (item.page_path, item.user_agent, item.viewport_width) == ("/plan", "Mozilla/5.0", 390)


def test_context_fields_are_optional(client, db_session):
    client.post("/feedback", data=VALID)

    [item] = _items(db_session)
    assert (item.page_path, item.user_agent, item.viewport_width, item.screenshot_key) == (None, None, None, None)


@pytest.mark.parametrize("missing", ["title", "body", "type"])
def test_a_missing_required_field_is_422(client, db_session, missing):
    data = {k: v for k, v in VALID.items() if k != missing}

    assert client.post("/feedback", data=data).status_code == 422
    assert _items(db_session) == []


@pytest.mark.parametrize("field", ["title", "body"])
def test_a_blank_title_or_body_is_422(client, db_session, field):
    assert client.post("/feedback", data={**VALID, field: "   "}).status_code == 422
    assert _items(db_session) == []


def test_an_unknown_type_is_422(client, db_session):
    assert client.post("/feedback", data={**VALID, "type": "praise"}).status_code == 422
    assert _items(db_session) == []


@pytest.mark.parametrize("value", ["wide", "-1"])
def test_an_invalid_viewport_width_is_422(client, value):
    assert client.post("/feedback", data={**VALID, "viewport_width": value}).status_code == 422


@pytest.mark.parametrize(
    ("field", "limit"),
    [("title", 200), ("body", 10_000), ("page_path", 500), ("user_agent", 500)],
)
def test_text_fields_are_length_bounded(client, db_session, field, limit):
    at_limit = client.post("/feedback", data={**VALID, field: "x" * limit})
    over_limit = client.post("/feedback", data={**VALID, field: "x" * (limit + 1)})

    assert at_limit.status_code == 201
    assert over_limit.status_code == 422
    assert len(_items(db_session)) == 1


def test_a_screenshot_is_stored_under_feedback_and_readable_back(client, db_session):
    response = client.post("/feedback", data=VALID, files={"screenshot": ("shot.png", b"pngbytes", "image/png")})

    assert response.status_code == 201
    [item] = _items(db_session)
    assert item.screenshot_key.startswith("feedback/")
    assert storage.open_image(item.screenshot_key) == (b"pngbytes", "image/png")


def test_an_empty_screenshot_part_counts_as_no_screenshot(client, db_session):
    response = client.post("/feedback", data=VALID, files={"screenshot": ("", b"", "application/octet-stream")})

    assert response.status_code == 201
    [item] = _items(db_session)
    assert item.screenshot_key is None


def test_a_non_image_screenshot_is_400_and_writes_no_row(client, db_session, tmp_path):
    response = client.post("/feedback", data=VALID, files={"screenshot": ("notes.txt", b"hello", "text/plain")})

    assert response.status_code == 400
    assert _items(db_session) == []
    assert list(tmp_path.iterdir()) == []


def test_an_oversized_screenshot_is_413_and_writes_no_row(client, db_session, tmp_path):
    big = b"x" * (storage.MAX_IMAGE_BYTES + 1)

    response = client.post("/feedback", data=VALID, files={"screenshot": ("big.png", big, "image/png")})

    assert response.status_code == 413
    assert _items(db_session) == []
    assert list(tmp_path.iterdir()) == []


def test_a_screenshot_exactly_at_the_cap_is_accepted(client):
    exact = b"x" * storage.MAX_IMAGE_BYTES

    response = client.post("/feedback", data=VALID, files={"screenshot": ("ok.png", exact, "image/png")})

    assert response.status_code == 201


def test_anonymous_is_401(anon, db_session):
    assert anon.post("/feedback", data=VALID).status_code == 401
    assert _items(db_session) == []


def test_submission_is_rate_limited_per_user(db_session, user, monkeypatch):
    """The limiter keys off the bearer header, not the dependency override."""
    import auth_users

    monkeypatch.setattr(app.state.share_limiter, "enabled", True)
    ratelimit.limiter.reset()
    token = auth_users.create_access_token(str(user.id))
    client = client_as(db_session, user)
    budget = int(ratelimit.FEEDBACK_RATE_LIMIT.split("/")[0])
    try:
        statuses = [
            client.post("/feedback", data=VALID, headers={"Authorization": f"Bearer {token}"}).status_code
            for _ in range(budget + 1)
        ]
    finally:
        app.dependency_overrides.clear()
        ratelimit.limiter.reset()

    assert statuses[:-1] == [201] * budget
    assert statuses[-1] == 429
    assert len(_items(db_session)) == budget
