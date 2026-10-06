"""The user feedback tables: ``feedback_items``, ``feedback_tags`` and their link.

Named ``user_feedback`` throughout because ``feedback`` already means the
meal-plan accept/reject signal (``tests/test_feedback.py``).
"""

from datetime import datetime

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError

from models import (
    FEEDBACK_PRIORITY_VALUES,
    FEEDBACK_STATUS_VALUES,
    FEEDBACK_TYPE_VALUES,
    FeedbackItem,
    FeedbackTag,
    User,
    feedback_item_tags,
)


def _item(session, **overrides):
    fields = {
        "ref_code": "FB-test",
        "title": "Plan page is blank",
        "body": "Nothing renders.",
        "type": "issue",
    }
    fields.update(overrides)
    item = FeedbackItem(**fields)
    session.add(item)
    session.flush()
    return item


def _link_count(session) -> int:
    return session.execute(select(func.count()).select_from(feedback_item_tags)).scalar_one()


def test_the_value_sets_are_the_ones_the_design_fixes():
    assert FEEDBACK_TYPE_VALUES == ("issue", "request", "improvement", "not_working")
    assert FEEDBACK_STATUS_VALUES == ("open", "in_progress", "closed_fixed", "closed_ignored")
    assert FEEDBACK_PRIORITY_VALUES == ("low", "normal", "high")


def test_a_new_item_is_open_normal_unseen_and_stamped(db_session):
    item = _item(db_session)

    db_session.refresh(item)
    assert item.status == "open"
    assert item.priority == "normal"
    assert item.seen is False
    assert isinstance(item.created_at, datetime)
    assert isinstance(item.updated_at, datetime)


def test_updated_at_moves_when_the_row_changes(db_session):
    item = _item(db_session)
    db_session.refresh(item)
    # ``now()`` is the transaction's start time, so back-date the stamp to see
    # the ``onupdate`` rewrite it.
    db_session.execute(
        text("UPDATE feedback_items SET updated_at = '2000-01-01' WHERE id = :id"), {"id": item.id}
    )
    db_session.refresh(item)

    item.status = "in_progress"
    db_session.flush()
    db_session.refresh(item)

    assert item.updated_at.year > 2000


@pytest.mark.parametrize(
    "column, value",
    [("type", "bug"), ("status", "closed"), ("priority", "urgent")],
)
def test_values_outside_the_sets_are_rejected_by_the_database(db_session, column, value):
    with pytest.raises(IntegrityError):
        _item(db_session, **{column: value})


@pytest.mark.parametrize("value", FEEDBACK_TYPE_VALUES)
def test_every_type_is_accepted(db_session, value):
    assert _item(db_session, type=value, ref_code=f"FB-{value}").type == value


def test_ref_codes_are_unique(db_session):
    _item(db_session, ref_code="FB-1")

    with pytest.raises(IntegrityError):
        _item(db_session, ref_code="FB-1")


def test_an_item_outlives_the_account_that_filed_it(db_session, user):
    item = _item(db_session, user_id=user.id)

    db_session.execute(text("DELETE FROM users WHERE id = :id"), {"id": user.id})
    db_session.expire_all()

    assert db_session.get(FeedbackItem, item.id).user_id is None


def test_tag_names_are_stored_normalized(db_session):
    tag = FeedbackTag(name="  Meal   Plan\tPage ")
    db_session.add(tag)
    db_session.flush()
    db_session.expire(tag)

    assert tag.name == "meal plan page"


def test_two_tags_that_normalize_alike_cannot_coexist(db_session):
    db_session.add(FeedbackTag(name="mobile"))
    db_session.flush()

    db_session.add(FeedbackTag(name=" MOBILE "))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_items_carry_tags_and_deleting_either_side_drops_the_link(db_session):
    first = _item(db_session, ref_code="FB-a")
    second = _item(db_session, ref_code="FB-b")
    mobile, planner = FeedbackTag(name="mobile"), FeedbackTag(name="planner")
    first.tags.extend([mobile, planner])
    second.tags.append(mobile)
    db_session.flush()
    assert _link_count(db_session) == 3

    # Deleted with SQL so the database's ON DELETE CASCADE is what is tested,
    # not the ORM's own bookkeeping.
    db_session.execute(text("DELETE FROM feedback_items WHERE id = :id"), {"id": first.id})
    assert _link_count(db_session) == 1
    db_session.execute(text("DELETE FROM feedback_tags WHERE id = :id"), {"id": mobile.id})
    assert _link_count(db_session) == 0


def test_feedback_is_not_owner_scoped(db_session):
    """``user_id`` is provenance (nullable, SET NULL), not the owner FK factory's CASCADE."""
    fk = next(iter(FeedbackItem.__table__.c.user_id.foreign_keys))
    assert fk.ondelete == "SET NULL"
    assert FeedbackItem.__table__.c.user_id.nullable is True
    assert User.__table__.name == fk.column.table.name
