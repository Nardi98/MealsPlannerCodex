"""DM-1: the testing seed must cover every new sharing column and table.

CLAUDE.md makes updating ``seed_testing_data.py`` part of any schema change, so
these assertions are the executable form of that rule.
"""

from datetime import datetime

from sqlalchemy import select

import usernames
from models import Recipe, RecipeShare, User
from scripts.seed_testing_data import populate
from scripts.seed_user_data import PROFILES, seed_profiles


def test_every_seeded_user_has_a_valid_unique_username(db_session):
    populate(db_session)

    handles = [
        u.username for u in db_session.execute(select(User)).scalars()
    ]
    assert len(handles) >= 3, "shares need somewhere to go"
    assert len(handles) == len(set(handles))
    for handle in handles:
        assert usernames.validate(handle) == handle


def test_the_seed_produces_private_and_unlisted_recipes(db_session):
    populate(db_session)

    states = {
        r.visibility for r in db_session.execute(select(Recipe)).scalars()
    }
    assert "private" in states
    assert "unlisted" in states
    # VIS-5: nothing in this release may reach ``public``.
    assert "public" not in states


def test_the_seed_produces_one_active_share_of_each_mode(db_session):
    populate(db_session)
    now = datetime.utcnow()

    active = [
        s
        for s in db_session.execute(select(RecipeShare)).scalars()
        if s.revoked_at is None and (s.expires_at is None or s.expires_at > now)
    ]
    assert {s.mode for s in active} == {"link", "person"}


def test_the_seed_produces_an_expired_and_a_revoked_share(db_session):
    populate(db_session)
    now = datetime.utcnow()
    shares = db_session.execute(select(RecipeShare)).scalars().all()

    assert any(s.revoked_at is not None for s in shares)
    assert any(s.expires_at is not None and s.expires_at < now for s in shares)


def test_every_seeded_share_stores_only_a_digest(db_session):
    """SH-3: 64 hex characters, never anything a browser could use."""
    populate(db_session)

    for share in db_session.execute(select(RecipeShare)).scalars():
        assert len(share.token_hash) == 64
        assert all(c in "0123456789abcdef" for c in share.token_hash)


def test_a_person_mode_seeded_share_names_a_recipient(db_session):
    populate(db_session)

    for share in db_session.execute(select(RecipeShare)).scalars():
        if share.mode == "person":
            assert share.recipient_user_id or share.recipient_email


def test_every_unlisted_seeded_recipe_has_an_active_share(db_session):
    """VIS-4/VIS-7: unlisted without a live share would be incoherent."""
    populate(db_session)
    now = datetime.utcnow()

    live_recipe_ids = {
        s.recipe_id
        for s in db_session.execute(select(RecipeShare)).scalars()
        if s.revoked_at is None and (s.expires_at is None or s.expires_at > now)
    }
    for recipe in db_session.execute(select(Recipe)).scalars():
        if recipe.visibility == "unlisted":
            assert recipe.id in live_recipe_ids


def test_the_seed_produces_a_copy_carrying_full_attribution(db_session):
    populate(db_session)

    copies = [
        r
        for r in db_session.execute(select(Recipe)).scalars()
        if r.source_recipe_id is not None
    ]
    assert copies, "DM-1 requires at least one copy"

    copy = copies[0]
    assert copy.source_user_id is not None
    assert copy.source_author_username
    assert copy.source_recipe_title
    assert copy.copied_at is not None
    # CP-4: a copy is private and has no copies of its own.
    assert copy.visibility == "private"
    assert copy.copy_count == 0
    # CP-2/CP-3: owned by the copier, not the source author.
    assert copy.user_id != copy.source_user_id


def test_the_source_of_a_seeded_copy_counts_it(db_session):
    """AT-7: the owner sees "copied N times"."""
    populate(db_session)

    copy = next(
        r
        for r in db_session.execute(select(Recipe)).scalars()
        if r.source_recipe_id is not None
    )
    source = db_session.get(Recipe, copy.source_recipe_id)
    assert source.copy_count >= 1


def test_a_seeded_copy_carries_no_planner_history(db_session):
    """CP-7."""
    populate(db_session)

    for recipe in db_session.execute(select(Recipe)).scalars():
        if recipe.source_recipe_id is not None:
            assert recipe.score is None
            assert recipe.date_last_consumed is None
            assert recipe.date_last_rejected is None


def test_every_profile_declares_a_username(db_session):
    for profile in PROFILES:
        assert usernames.validate(profile.username) == profile.username


def test_seeded_profiles_get_their_usernames(db_session):
    seed_profiles(db_session)

    for profile in PROFILES:
        user = db_session.execute(
            select(User).where(User.email == profile.email)
        ).scalar_one()
        assert user.username == profile.username
