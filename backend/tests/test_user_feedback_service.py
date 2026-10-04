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


# --- reading one item and triage ---------------------------------------------


def test_get_item_returns_the_item(db_session, user):
    item = _submit(db_session, user)

    assert user_feedback.get_item(db_session, item.id) is item


def test_get_item_raises_not_found_for_an_unknown_id(db_session):
    with pytest.raises(user_feedback.FeedbackItemNotFound):
        user_feedback.get_item(db_session, 999_999)


def test_not_found_errors_are_lookup_errors():
    assert issubclass(user_feedback.FeedbackItemNotFound, LookupError)
    assert issubclass(user_feedback.FeedbackTagNotFound, LookupError)


def test_mark_seen_marks_read_and_unread_without_touching_status(db_session, user):
    item = _submit(db_session, user)

    user_feedback.mark_seen(db_session, item)
    db_session.expire_all()
    assert (item.seen, item.status) == (True, "open")

    user_feedback.mark_seen(db_session, item, seen=False)
    db_session.expire_all()
    assert (item.seen, item.status) == (False, "open")


def test_closing_an_item_does_not_mark_it_seen(db_session, user):
    item = _submit(db_session, user)

    user_feedback.set_status(db_session, item, "closed_fixed")
    db_session.expire_all()

    assert (item.status, item.seen) == ("closed_fixed", False)


def test_set_status_rejects_an_unknown_status(db_session, user):
    item = _submit(db_session, user)

    with pytest.raises(ValueError):
        user_feedback.set_status(db_session, item, "done")


def test_set_priority_stores_the_priority(db_session, user):
    item = _submit(db_session, user)

    user_feedback.set_priority(db_session, item, "high")
    db_session.expire_all()

    assert item.priority == "high"


def test_set_priority_rejects_an_unknown_priority(db_session, user):
    item = _submit(db_session, user)

    with pytest.raises(ValueError):
        user_feedback.set_priority(db_session, item, "urgent")


def test_set_notes_stores_stripped_notes_and_none_or_blank_clears_them(db_session, user):
    item = _submit(db_session, user)

    user_feedback.set_notes(db_session, item, "  check on iOS  ")
    db_session.expire_all()
    assert item.admin_notes == "check on iOS"

    user_feedback.set_notes(db_session, item, None)
    db_session.expire_all()
    assert item.admin_notes is None

    user_feedback.set_notes(db_session, item, "x")
    user_feedback.set_notes(db_session, item, "   ")
    db_session.expire_all()
    assert item.admin_notes is None


def test_a_triage_mutation_does_not_move_updated_at_backwards(db_session, user):
    item = _submit(db_session, user)
    before = item.updated_at

    user_feedback.set_priority(db_session, item, "low")
    db_session.expire_all()

    assert item.updated_at >= before


def test_unseen_count_matches_the_rows(db_session, user):
    first = _submit(db_session, user)
    _submit(db_session, user)
    _submit(db_session, user)
    assert user_feedback.unseen_count(db_session) == 3

    user_feedback.mark_seen(db_session, first)

    assert user_feedback.unseen_count(db_session) == 2
