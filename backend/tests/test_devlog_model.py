"""The ``dev_log_entries`` table: a developer-only, per-user event log."""

from datetime import datetime

from sqlalchemy import inspect

from models import DevLogEntry, Recipe, User


def test_an_entry_is_stamped_and_keeps_its_json_payload(db_session, user):
    entry = DevLogEntry(
        user_id=user.id, channel="planner", event="generate", payload={"slots": [{"score": 1.5}]}
    )
    db_session.add(entry)
    db_session.flush()
    db_session.refresh(entry)

    assert isinstance(entry.created_at, datetime)
    assert entry.payload == {"slots": [{"score": 1.5}]}


def test_entries_go_with_their_owner(db_session, user):
    db_session.add(DevLogEntry(user_id=user.id, channel="planner", event="x", payload={}))
    db_session.flush()

    db_session.delete(db_session.get(User, user.id))
    db_session.flush()
    db_session.expire_all()

    assert db_session.query(DevLogEntry).count() == 0


def test_the_lookup_index_is_named(db_session):
    names = {ix["name"] for ix in inspect(db_session.bind).get_indexes("dev_log_entries")}
    assert "ix_dev_log_entries_user_channel_created" in names


def test_recipe_tracks_when_it_was_last_suggested(db_session):
    recipe = Recipe(title="Soup")
    db_session.add(recipe)
    db_session.flush()
    db_session.refresh(recipe)

    assert recipe.date_last_suggested is None
    assert not hasattr(recipe, "date_last_consumed")
