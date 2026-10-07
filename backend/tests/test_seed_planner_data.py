"""The testing seed must exercise the planner's memory and the developer log.

CLAUDE.md makes updating ``seed_testing_data.py`` part of any schema change; these
assertions are the executable form of that rule for ``date_last_suggested``,
``date_last_rejected`` and ``dev_log_entries``.
"""

from sqlalchemy import select

from models import DevLogEntry, Recipe, User
from scripts.seed_testing_data import DEMO_USER_EMAIL, populate


def _demo(session) -> User:
    return session.execute(select(User).where(User.email == DEMO_USER_EMAIL)).scalar_one()


def test_some_demo_recipes_carry_planner_memory(db_session):
    populate(db_session)
    demo = _demo(db_session)
    recipes = db_session.execute(select(Recipe).where(Recipe.user_id == demo.id)).scalars().all()

    assert any(r.date_last_suggested for r in recipes)
    assert any(r.date_last_rejected for r in recipes)


def test_the_demo_account_has_planner_log_entries(db_session):
    populate(db_session)
    demo = _demo(db_session)
    entries = db_session.execute(
        select(DevLogEntry).where(DevLogEntry.user_id == demo.id)
    ).scalars().all()

    assert entries
    assert {e.channel for e in entries} == {"planner"}
    assert {"generate", "feedback"} <= {e.event for e in entries}
