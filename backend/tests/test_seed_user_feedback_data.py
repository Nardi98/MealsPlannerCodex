"""The testing seed must leave a user feedback inbox worth triaging.

CLAUDE.md makes updating ``seed_testing_data.py`` part of any schema change;
these assertions are the executable form of that rule for the feedback tables.
A freshly composed database should exercise every filter and badge the admin
inbox has: each type, status and priority, read and unread, tagged and not, and
one item with a screenshot that actually opens.
"""

from sqlalchemy import select

import storage
from models import (
    FEEDBACK_PRIORITY_VALUES,
    FEEDBACK_STATUS_VALUES,
    FEEDBACK_TYPE_VALUES,
    FeedbackItem,
    FeedbackTag,
    User,
)
from scripts.seed_testing_data import populate


def _items(session) -> list[FeedbackItem]:
    populate(session)
    return session.execute(select(FeedbackItem).order_by(FeedbackItem.id)).scalars().all()


def test_the_seed_spans_every_type_status_and_priority(db_session):
    items = _items(db_session)

    assert {item.type for item in items} == set(FEEDBACK_TYPE_VALUES)
    assert {item.status for item in items} == set(FEEDBACK_STATUS_VALUES)
    assert {item.priority for item in items} == set(FEEDBACK_PRIORITY_VALUES)
    assert {item.seen for item in items} == {True, False}


def test_every_ref_code_is_derived_from_the_id(db_session):
    for item in _items(db_session):
        assert item.ref_code == f"FB-{item.id}"


def test_items_are_filed_by_seeded_accounts(db_session):
    items = _items(db_session)

    filers = {db_session.get(User, item.user_id).username for item in items}
    assert len(filers) >= 2


def test_some_items_carry_context_notes_and_tags(db_session):
    items = _items(db_session)

    assert any(item.page_path and item.viewport_width and item.user_agent for item in items)
    assert any(item.admin_notes for item in items)
    assert sum(1 for item in items if item.tags) >= 2
    assert db_session.execute(select(FeedbackTag)).scalars().all()


def test_one_item_carries_a_screenshot_that_opens(db_session, tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "MEDIA_DIR", tmp_path)

    with_shots = [item for item in _items(db_session) if item.screenshot_key]

    assert len(with_shots) == 1
    key = with_shots[0].screenshot_key
    assert key.startswith("feedback/")
    data, content_type = storage.open_image(key)
    assert content_type == "image/png"
    assert data.startswith(b"\x89PNG\r\n\x1a\n")
