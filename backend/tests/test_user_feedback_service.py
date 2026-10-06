"""Tests for ``user_feedback``, the domain module behind the feedback routers.

Every service function commits; ``db_session`` scopes those commits to a
SAVEPOINT and rolls the outer transaction back, so nothing leaks between tests.
"""

from datetime import datetime

import pytest
from sqlalchemy import func, inspect, select, update

import storage
import user_feedback
from models import FeedbackItem, FeedbackTag

PNG = b"\x89PNG\r\n\x1a\nfake"


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


def test_update_item_applies_every_field_passed(db_session, user):
    item = _submit(db_session, user)

    user_feedback.update_item(
        db_session, item, status="in_progress", priority="high", admin_notes=" n ", tags=["UI"], seen=True
    )
    db_session.expire_all()

    assert (item.status, item.priority, item.admin_notes, item.seen) == ("in_progress", "high", "n", True)
    assert [tag.name for tag in item.tags] == ["ui"]


def test_update_item_leaves_fields_not_passed_alone(db_session, user):
    item = _submit(db_session, user)
    user_feedback.set_notes(db_session, item, "keep me")

    user_feedback.update_item(db_session, item, priority="low")
    db_session.expire_all()

    assert (item.priority, item.status, item.admin_notes, item.seen) == ("low", "open", "keep me", False)


def test_update_item_with_one_bad_value_changes_nothing(db_session, user):
    item = _submit(db_session, user)

    with pytest.raises(ValueError):
        user_feedback.update_item(db_session, item, status="in_progress", priority="urgent")
    db_session.expire_all()

    assert (item.status, item.priority) == ("open", "normal")


LONG_AGO = datetime(2000, 1, 1)


def _age(session, item):
    """Backdate ``updated_at``, so a fresh stamp is observable inside one transaction."""
    session.execute(update(FeedbackItem).where(FeedbackItem.id == item.id).values(updated_at=LONG_AGO))
    session.expire_all()


@pytest.mark.parametrize(
    "mutate",
    [
        lambda s, i: user_feedback.mark_seen(s, i),
        lambda s, i: user_feedback.set_status(s, i, "in_progress"),
        lambda s, i: user_feedback.set_priority(s, i, "low"),
        lambda s, i: user_feedback.set_notes(s, i, "note"),
    ],
    ids=["seen", "status", "priority", "notes"],
)
def test_a_triage_mutation_stamps_updated_at(db_session, user, mutate):
    item = _submit(db_session, user)
    _age(db_session, item)

    mutate(db_session, item)
    db_session.expire_all()

    assert item.updated_at > LONG_AGO


def test_unseen_count_matches_the_rows(db_session, user):
    first = _submit(db_session, user)
    _submit(db_session, user)
    _submit(db_session, user)
    assert user_feedback.unseen_count(db_session) == 3

    user_feedback.mark_seen(db_session, first)

    assert user_feedback.unseen_count(db_session) == 2


# --- tags ------------------------------------------------------------------


def _tag_count(session) -> int:
    return session.execute(select(func.count()).select_from(FeedbackTag)).scalar_one()


def _names(item):
    return [tag.name for tag in item.tags]


def test_set_tags_creates_missing_tags(db_session, user):
    item = _submit(db_session, user)

    user_feedback.set_tags(db_session, item, ["mobile", "shopping list"])
    db_session.expire_all()

    assert _names(item) == ["mobile", "shopping list"]
    assert _tag_count(db_session) == 2


def test_names_that_normalize_alike_are_one_tag(db_session, user):
    first = _submit(db_session, user)
    second = _submit(db_session, user)

    user_feedback.set_tags(db_session, first, ["Mobile", "mobile ", "mobile"])
    user_feedback.set_tags(db_session, second, ["  MOBILE"])
    db_session.expire_all()

    assert _names(first) == ["mobile"]
    assert _names(second) == ["mobile"]
    assert _tag_count(db_session) == 1


def test_set_tags_replaces_the_set(db_session, user):
    item = _submit(db_session, user)
    user_feedback.set_tags(db_session, item, ["a", "b"])

    user_feedback.set_tags(db_session, item, ["b", "c"])
    db_session.expire_all()

    assert _names(item) == ["b", "c"]


def test_set_tags_with_no_names_removes_every_tag_but_keeps_the_tags(db_session, user):
    item = _submit(db_session, user)
    user_feedback.set_tags(db_session, item, ["a", "b"])

    user_feedback.set_tags(db_session, item, [])
    db_session.expire_all()

    assert item.tags == []
    assert _tag_count(db_session) == 2


def test_set_tags_ignores_blank_names(db_session, user):
    item = _submit(db_session, user)

    user_feedback.set_tags(db_session, item, ["", "   ", "ui"])
    db_session.expire_all()

    assert _names(item) == ["ui"]
    assert _tag_count(db_session) == 1


def test_set_tags_stamps_updated_at_although_no_item_column_changes(db_session, user):
    # A tag change only writes the join table, so ``onupdate`` alone would not fire.
    item = _submit(db_session, user)
    _age(db_session, item)

    user_feedback.set_tags(db_session, item, ["ui"])
    db_session.expire_all()

    assert item.updated_at > LONG_AGO


def test_list_tags_is_sorted_by_name(db_session, user):
    item = _submit(db_session, user)
    user_feedback.set_tags(db_session, item, ["zeta", "alpha", "mid"])

    assert [tag.name for tag in user_feedback.list_tags(db_session)] == ["alpha", "mid", "zeta"]


def test_get_tag_returns_the_tag_or_raises_not_found(db_session, user):
    item = _submit(db_session, user)
    user_feedback.set_tags(db_session, item, ["ui"])
    tag = item.tags[0]

    assert user_feedback.get_tag(db_session, tag.id) is tag
    with pytest.raises(user_feedback.FeedbackTagNotFound):
        user_feedback.get_tag(db_session, 999_999)


def test_rename_tag_normalizes_the_new_name(db_session, user):
    item = _submit(db_session, user)
    user_feedback.set_tags(db_session, item, ["ui"])

    user_feedback.rename_tag(db_session, item.tags[0], "  User   Interface ")
    db_session.expire_all()

    assert _names(item) == ["user interface"]


def test_rename_tag_to_its_own_name_in_another_case_is_fine(db_session, user):
    item = _submit(db_session, user)
    user_feedback.set_tags(db_session, item, ["ui"])

    tag = user_feedback.rename_tag(db_session, item.tags[0], "UI")

    assert tag.name == "ui"


def test_rename_tag_to_another_tags_name_raises_taken(db_session, user):
    item = _submit(db_session, user)
    user_feedback.set_tags(db_session, item, ["ui", "mobile"])
    ui = next(tag for tag in item.tags if tag.name == "ui")

    with pytest.raises(user_feedback.FeedbackTagNameTaken):
        user_feedback.rename_tag(db_session, ui, " Mobile")

    db_session.expire_all()
    assert sorted(_names(item)) == ["mobile", "ui"]


def _ids(items):
    return [item.id for item in items]


def test_list_items_is_newest_first_with_ties_broken_by_id(db_session, user):
    # Inside one transaction ``now()`` is constant, so every created_at ties.
    first, second, third = (_submit(db_session, user) for _ in range(3))
    db_session.execute(
        update(FeedbackItem).where(FeedbackItem.id == first.id).values(created_at=datetime(2999, 1, 1))
    )

    assert _ids(user_feedback.list_items(db_session)) == [first.id, third.id, second.id]


def test_list_items_filters_by_status_type_priority_and_seen(db_session, user):
    plain = _submit(db_session, user)
    request = _submit(db_session, user, type="request")
    closed = _submit(db_session, user)
    user_feedback.set_status(db_session, closed, "closed_ignored")
    urgent = _submit(db_session, user)
    user_feedback.set_priority(db_session, urgent, "high")
    user_feedback.mark_seen(db_session, urgent)

    assert _ids(user_feedback.list_items(db_session, status="closed_ignored")) == [closed.id]
    assert _ids(user_feedback.list_items(db_session, type="request")) == [request.id]
    assert _ids(user_feedback.list_items(db_session, priority="high")) == [urgent.id]
    assert _ids(user_feedback.list_items(db_session, seen=True)) == [urgent.id]
    assert _ids(user_feedback.list_items(db_session, seen=False)) == [closed.id, request.id, plain.id]


def test_list_items_filters_by_a_normalized_tag_name(db_session, user):
    tagged = _submit(db_session, user)
    _submit(db_session, user)
    user_feedback.set_tags(db_session, tagged, ["mobile", "ui"])

    assert _ids(user_feedback.list_items(db_session, tag="  Mobile ")) == [tagged.id]
    assert user_feedback.list_items(db_session, tag="nonexistent") == []


def test_list_items_filters_compose(db_session, user):
    match = _submit(db_session, user)
    wrong_type = _submit(db_session, user, type="request")
    untagged = _submit(db_session, user)
    for item in (match, wrong_type):
        user_feedback.set_tags(db_session, item, ["ui"])

    found = user_feedback.list_items(db_session, type="issue", tag="ui", status="open", seen=False)

    assert _ids(found) == [match.id]
    assert untagged.id not in _ids(found)


def test_list_items_loads_tags_and_author_up_front(db_session, user):
    item = _submit(db_session, user)
    user_feedback.set_tags(db_session, item, ["ui"])
    db_session.expire_all()

    [listed] = user_feedback.list_items(db_session)

    assert {"tags", "author"}.isdisjoint(inspect(listed).unloaded)
    assert listed.author.email == user.email


def test_rename_tag_rejects_a_blank_name(db_session, user):
    item = _submit(db_session, user)
    user_feedback.set_tags(db_session, item, ["ui"])

    with pytest.raises(ValueError):
        user_feedback.rename_tag(db_session, item.tags[0], "   ")
