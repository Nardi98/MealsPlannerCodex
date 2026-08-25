"""§11.3: the ``recipe_shares`` table's columns and constraints.

Constraints only -- token minting, resolution, and the routes belong to later
phases. Nothing here constructs a raw token: the model only ever sees a digest.
"""

import hashlib
from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

import crud
from models import SHARE_MODES, RecipeShare


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


@pytest.fixture
def recipe(db_session, user):
    return crud.create_recipe(
        db_session, title="Ragu", user_id=user.id
    )


def test_share_modes_are_link_and_person():
    assert SHARE_MODES == ("link", "person")


def test_a_link_share_needs_no_recipient(db_session, user, recipe):
    """SH-5: a recipient is optional in link mode."""
    share = RecipeShare(
        recipe_id=recipe.id,
        created_by_user_id=user.id,
        token_hash=_digest("t1"),
        mode="link",
    )
    db_session.add(share)
    db_session.flush()
    assert share.id is not None
    assert share.revoked_at is None
    assert share.expires_at is None
    assert share.last_viewed_at is None
    assert share.dismissed_by_recipient_at is None
    assert share.created_at is not None


def test_a_person_share_requires_a_recipient(db_session, user, recipe):
    """§11.3's CHECK constraint, at the database."""
    db_session.add(
        RecipeShare(
            recipe_id=recipe.id,
            created_by_user_id=user.id,
            token_hash=_digest("t2"),
            mode="person",
        )
    )
    with pytest.raises(Exception):
        db_session.flush()
    db_session.rollback()


def test_a_person_share_accepts_a_recipient_account(db_session, user, other_user):
    recipe = crud.create_recipe(
        db_session, title="Ragu", user_id=user.id
    )
    share = RecipeShare(
        recipe_id=recipe.id,
        created_by_user_id=user.id,
        token_hash=_digest("t3"),
        mode="person",
        recipient_user_id=other_user.id,
    )
    db_session.add(share)
    db_session.flush()
    assert share.recipient_user_id == other_user.id


def test_a_person_share_accepts_a_recipient_email(db_session, user, recipe):
    share = RecipeShare(
        recipe_id=recipe.id,
        created_by_user_id=user.id,
        token_hash=_digest("t4"),
        mode="person",
        recipient_email="friend@example.com",
    )
    db_session.add(share)
    db_session.flush()
    assert share.recipient_email == "friend@example.com"


def test_token_hash_is_unique(db_session, user, recipe):
    """SH-3: one digest, one share."""
    for _ in range(2):
        db_session.add(
            RecipeShare(
                recipe_id=recipe.id,
                created_by_user_id=user.id,
                token_hash=_digest("same"),
                mode="link",
            )
        )
    with pytest.raises(Exception):
        db_session.flush()
    db_session.rollback()


def test_an_unknown_mode_is_rejected(db_session, user, recipe):
    db_session.add(
        RecipeShare(
            recipe_id=recipe.id,
            created_by_user_id=user.id,
            token_hash=_digest("t5"),
            mode="broadcast",
        )
    )
    with pytest.raises(Exception):
        db_session.flush()
    db_session.rollback()


def test_expiry_and_revocation_are_storable(db_session, user, recipe):
    """SH-9 / SH-21: both are plain timestamps read at resolution time."""
    now = datetime.utcnow()
    share = RecipeShare(
        recipe_id=recipe.id,
        created_by_user_id=user.id,
        token_hash=_digest("t6"),
        mode="link",
        expires_at=now + timedelta(days=7),
        revoked_at=now,
    )
    db_session.add(share)
    db_session.flush()
    assert share.expires_at > now
    assert share.revoked_at == now


def test_deleting_the_recipe_revokes_its_shares(db_session, user, recipe):
    """SH-25 through the ordinary deletion path."""
    db_session.add(
        RecipeShare(
            recipe_id=recipe.id,
            created_by_user_id=user.id,
            token_hash=_digest("t7"),
            mode="link",
        )
    )
    db_session.flush()

    assert crud.delete_recipe(db_session, recipe.id, user.id) is True

    remaining = db_session.execute(select(RecipeShare)).scalars().all()
    assert all(s.revoked_at is not None for s in remaining)


def test_revoke_shares_for_recipe_leaves_already_revoked_stamps_alone(
    db_session, user, recipe
):
    earlier = datetime.utcnow() - timedelta(days=3)
    share = RecipeShare(
        recipe_id=recipe.id,
        created_by_user_id=user.id,
        token_hash=_digest("t8"),
        mode="link",
        revoked_at=earlier,
    )
    db_session.add(share)
    db_session.flush()

    crud.revoke_shares_for_recipe(db_session, recipe.id)
    assert share.revoked_at == earlier


def test_share_repr_never_exposes_a_digest(db_session, user, recipe):
    """Defence in depth: nothing token-shaped may reach a log line."""
    share = RecipeShare(
        recipe_id=recipe.id,
        created_by_user_id=user.id,
        token_hash=_digest("secret-token"),
        mode="link",
    )
    db_session.add(share)
    db_session.flush()
    assert _digest("secret-token") not in repr(share)
