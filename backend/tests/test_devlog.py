"""``devlog``: the generic developer log's write and read paths."""

from datetime import datetime, timedelta

import devlog
from models import DevLogEntry


def _stamp(session, entry_id, created_at):
    session.get(DevLogEntry, entry_id).created_at = created_at
    session.flush()


def test_record_adds_a_row_without_committing(db_session, user):
    entry = devlog.record(
        db_session, user_id=user.id, channel="planner", event="generate", payload={"n": 1}
    )

    assert entry.id is not None
    assert db_session.in_transaction()
    assert db_session.query(DevLogEntry).one().payload == {"n": 1}


def test_export_returns_one_users_rows_oldest_first(db_session, user, other_user):
    first = devlog.record(db_session, user_id=user.id, channel="planner", event="a", payload={})
    second = devlog.record(db_session, user_id=user.id, channel="planner", event="b", payload={})
    devlog.record(db_session, user_id=other_user.id, channel="planner", event="c", payload={})
    _stamp(db_session, first.id, datetime.utcnow() - timedelta(hours=2))
    _stamp(db_session, second.id, datetime.utcnow() - timedelta(hours=1))

    rows = devlog.export(db_session, user_id=user.id)

    assert [r["event"] for r in rows] == ["a", "b"]
    assert set(rows[0]) == {"id", "created_at", "channel", "event", "payload"}


def test_export_filters_by_channel(db_session, user):
    devlog.record(db_session, user_id=user.id, channel="planner", event="a", payload={})
    devlog.record(db_session, user_id=user.id, channel="other", event="b", payload={})

    rows = devlog.export(db_session, user_id=user.id, channel="other")

    assert [r["event"] for r in rows] == ["b"]


def test_record_prunes_the_users_rows_past_retention(db_session, user, other_user):
    now = datetime.utcnow()
    stale = devlog.record(db_session, user_id=user.id, channel="planner", event="old", payload={})
    edge = devlog.record(db_session, user_id=user.id, channel="planner", event="edge", payload={})
    theirs = devlog.record(
        db_session, user_id=other_user.id, channel="planner", event="theirs", payload={}
    )
    _stamp(db_session, stale.id, now - timedelta(days=devlog.RETENTION_DAYS, hours=1))
    _stamp(db_session, edge.id, now - timedelta(days=devlog.RETENTION_DAYS) + timedelta(hours=1))
    _stamp(db_session, theirs.id, now - timedelta(days=devlog.RETENTION_DAYS + 5))

    devlog.record(db_session, user_id=user.id, channel="planner", event="new", payload={})

    mine = [r["event"] for r in devlog.export(db_session, user_id=user.id)]
    assert mine == ["edge", "new"]
    # Another account's rows are pruned by that account's own writes, not ours.
    assert [r["event"] for r in devlog.export(db_session, user_id=other_user.id)] == ["theirs"]


def test_retention_is_ninety_days():
    assert devlog.RETENTION_DAYS == 90
