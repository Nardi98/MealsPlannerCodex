"""Tests for ``user_feedback``, the domain module behind the feedback routers.

Every service function commits; ``db_session`` scopes those commits to a
SAVEPOINT and rolls the outer transaction back, so nothing leaks between tests.
"""

import pytest
from sqlalchemy import func, select

import storage
import user_feedback
from models import FeedbackItem

PNG = b"\x89PNG\r\n\x1a\nfake"


@pytest.fixture(autouse=True)
def _media(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "MEDIA_DIR", tmp_path)


def _count(session) -> int:
    return session.execute(select(func.count()).select_from(FeedbackItem)).scalar_one()


def _submit(session, user=None, **kwargs):
    fields = {"title": "Broken button", "body": "Nothing happens", "type": "issue"}
    fields.update(kwargs)
    return user_feedback.submit(session, user, **fields)


# --- submit ----------------------------------------------------------------


def test_submit_commits_a_row_with_a_ref_code_derived_from_its_id(db_session, user):
    item = _submit(db_session, user)

    db_session.expire_all()
    stored = db_session.get(FeedbackItem, item.id)
    assert stored.ref_code == f"FB-{item.id}"


def test_submit_stores_the_author_and_the_captured_context(db_session, user):
    item = _submit(
        db_session, user, page_path="/recipes", user_agent="Firefox", viewport_width=390
    )

    db_session.expire_all()
    stored = db_session.get(FeedbackItem, item.id)
    assert stored.user_id == user.id
    assert (stored.page_path, stored.user_agent, stored.viewport_width) == ("/recipes", "Firefox", 390)
    assert (stored.status, stored.priority, stored.seen) == ("open", "normal", False)


def test_submit_without_a_user_stores_no_author(db_session):
    item = _submit(db_session, None)

    assert item.user_id is None


def test_submit_strips_title_and_body(db_session, user):
    item = _submit(db_session, user, title="  Title  ", body="\n Body \n")

    assert (item.title, item.body) == ("Title", "Body")


@pytest.mark.parametrize("field", ["title", "body"])
@pytest.mark.parametrize("value", ["", "   ", None])
def test_submit_rejects_a_blank_title_or_body(db_session, user, field, value):
    with pytest.raises(ValueError):
        _submit(db_session, user, **{field: value})

    assert _count(db_session) == 0


def test_submit_rejects_an_unknown_type(db_session, user):
    with pytest.raises(ValueError):
        _submit(db_session, user, type="complaint")

    assert _count(db_session) == 0


def test_submit_stores_a_screenshot_under_the_feedback_prefix(db_session, user):
    item = _submit(db_session, user, screenshot=(PNG, "image/png"))

    assert item.screenshot_key.startswith("feedback/")
    assert storage.open_image(item.screenshot_key) == (PNG, "image/png")


def test_submit_with_an_unsupported_screenshot_writes_no_row(db_session, user):
    with pytest.raises(ValueError):
        _submit(db_session, user, screenshot=(b"%PDF", "application/pdf"))

    assert _count(db_session) == 0


def test_submit_without_a_screenshot_stores_no_key(db_session, user):
    assert _submit(db_session, user).screenshot_key is None
