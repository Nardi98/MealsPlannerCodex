"""Domain tests for ``shares`` -- the capability layer guarding private recipes.

Every requirement referenced here comes from
``docs/superpowers/specs/2026-08-19-recipe-sharing-part1-user-to-user.md``.
"""
import hashlib
from datetime import datetime, timedelta

import pytest

import crud
import models
import shares


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def _share(session, recipe, owner, **kw):
    return shares.create_share(session, recipe=recipe, owner=owner, **kw)


class _FakeURL:
    def __init__(self, scheme, netloc):
        self.scheme = scheme
        self.netloc = netloc


class _FakeRequest:
    """The two attributes ``share_url`` reads off a Starlette ``Request``."""

    def __init__(self, scheme="http", host="testserver"):
        self.url = _FakeURL(scheme, host)
        self.base_url = f"{scheme}://{host}/"
        self.headers = {"host": host}


# --------------------------------------------------------------------------
# SH-2 / SH-3 -- token minting and storage
# --------------------------------------------------------------------------
def test_mint_token_is_high_entropy_and_unique():
    tokens = {shares.mint_token() for _ in range(200)}
    assert len(tokens) == 200
    # ``secrets.token_urlsafe(32)`` yields 43 base64url characters.
    assert all(len(t) >= 43 for t in tokens)


def test_hash_token_is_sha256_hex():
    token = "a-known-token"
    assert shares.hash_token(token) == hashlib.sha256(token.encode()).hexdigest()
    assert len(shares.hash_token(token)) == 64


def test_created_share_stores_only_the_hash(db_session, user, make_recipe):
    recipe = make_recipe("Ragu")
    share, token = _share(db_session, recipe, user, mode="link")

    assert share.token_hash == shares.hash_token(token)
    assert token not in repr(share)
    assert share.token_hash not in repr(share)


# --------------------------------------------------------------------------
# resolve -- SH-21, SH-22, SH-27
# --------------------------------------------------------------------------
def test_resolve_returns_the_share_for_a_valid_token(db_session, user, make_recipe):
    recipe = make_recipe("Ragu")
    share, token = _share(db_session, recipe, user, mode="link")

    resolved = shares.resolve(db_session, token)

    assert resolved is not None
    assert resolved.id == share.id


def test_resolve_returns_none_for_a_nonexistent_token(db_session):
    assert shares.resolve(db_session, shares.mint_token()) is None


def test_resolve_returns_none_for_a_revoked_token(db_session, user, make_recipe):
    recipe = make_recipe("Ragu")
    share, token = _share(db_session, recipe, user, mode="link")
    shares.revoke_share(db_session, share)

    assert shares.resolve(db_session, token) is None


def test_resolve_returns_none_for_an_expired_token(db_session, user, make_recipe):
    recipe = make_recipe("Ragu")
    _, token = _share(
        db_session,
        recipe,
        user,
        mode="link",
        expires_at=datetime.utcnow() - timedelta(seconds=1),
    )

    assert shares.resolve(db_session, token) is None


def test_resolve_failure_modes_are_indistinguishable(db_session, user, make_recipe):
    """SH-22: revoked, expired and nonexistent must be one single outcome."""
    revoked_recipe = make_recipe("Revoked")
    revoked, revoked_token = _share(db_session, revoked_recipe, user, mode="link")
    shares.revoke_share(db_session, revoked)

    expired_recipe = make_recipe("Expired")
    _, expired_token = _share(
        db_session,
        expired_recipe,
        user,
        mode="link",
        expires_at=datetime.utcnow() - timedelta(days=1),
    )

    outcomes = [
        shares.resolve(db_session, revoked_token),
        shares.resolve(db_session, expired_token),
        shares.resolve(db_session, shares.mint_token()),
        shares.resolve(db_session, "not-even-a-token"),
        shares.resolve(db_session, ""),
    ]
    assert outcomes == [None, None, None, None, None]
    # One identical result object, not three distinguishable ones.
    assert len({id(o) for o in outcomes}) == 1


def test_resolve_never_raises_for_malformed_input(db_session):
    for bad in ["", "   ", "x" * 5000, "../../etc/passwd", "%00"]:
        assert shares.resolve(db_session, bad) is None


def test_resolve_does_not_touch_the_recipe_of_an_invalid_share(
    db_session, user, make_recipe
):
    """An invalid token must not cause the recipe to be loaded at all."""
    recipe = make_recipe("Ragu")
    share, token = _share(db_session, recipe, user, mode="link")
    shares.revoke_share(db_session, share)
    db_session.flush()

    loaded = []
    original = shares._load_share_by_hash

    def _spy(session, digest):
        found = original(session, digest)
        if found is not None:
            loaded.append("recipe" in found.__dict__)
        return found

    shares._load_share_by_hash = _spy
    try:
        assert shares.resolve(db_session, token) is None
    finally:
        shares._load_share_by_hash = original
    assert loaded == [False]


# --------------------------------------------------------------------------
# VIS-6 -- promotion on first share
# --------------------------------------------------------------------------
def test_create_share_promotes_private_to_unlisted(db_session, user, make_recipe):
    recipe = make_recipe("Ragu")
    assert recipe.visibility == "private"

    _share(db_session, recipe, user, mode="link")

    assert recipe.visibility == "unlisted"


def test_create_share_never_promotes_to_public(db_session, user, make_recipe):
    """VIS-5: ``public`` is inert in this release."""
    recipe = make_recipe("Ragu")
    for _ in range(3):
        _share(db_session, recipe, user, mode="link")
    assert recipe.visibility == "unlisted"


def test_create_share_leaves_an_already_unlisted_recipe_alone(
    db_session, user, make_recipe
):
    recipe = make_recipe("Ragu")
    recipe.visibility = "unlisted"
    db_session.flush()

    _share(db_session, recipe, user, mode="link")

    assert recipe.visibility == "unlisted"


# --------------------------------------------------------------------------
# ownership
# --------------------------------------------------------------------------
def test_create_share_rejects_a_recipe_the_caller_does_not_own(
    db_session, user, other_user, make_recipe
):
    recipe = make_recipe("Ragu")

    with pytest.raises(PermissionError):
        _share(db_session, recipe, other_user, mode="link")

    assert recipe.visibility == "private"
    assert db_session.query(models.RecipeShare).count() == 0


def test_person_share_requires_a_recipient(db_session, user, make_recipe):
    recipe = make_recipe("Ragu")

    with pytest.raises(ValueError):
        _share(db_session, recipe, user, mode="person")


def test_create_share_rejects_an_unknown_mode(db_session, user, make_recipe):
    recipe = make_recipe("Ragu")

    with pytest.raises(ValueError):
        _share(db_session, recipe, user, mode="public-link")


def test_person_share_normalises_the_recipient_email(db_session, user, make_recipe):
    recipe = make_recipe("Ragu")

    share, _ = _share(
        db_session, recipe, user, mode="person", recipient_email="  Bob@Example.COM "
    )

    assert share.recipient_email == models.normalize_email("bob@example.com")


# --------------------------------------------------------------------------
# VIS-7 -- lazy demotion
# --------------------------------------------------------------------------
def test_revoking_the_last_share_demotes_to_private(db_session, user, make_recipe):
    recipe = make_recipe("Ragu")
    share, _ = _share(db_session, recipe, user, mode="link")

    shares.revoke_share(db_session, share)
    shares.demote_if_no_active_shares(db_session, recipe)

    assert recipe.visibility == "private"


def test_revoking_one_of_two_shares_keeps_it_unlisted(db_session, user, make_recipe):
    recipe = make_recipe("Ragu")
    first, _ = _share(db_session, recipe, user, mode="link")
    _share(db_session, recipe, user, mode="link")

    shares.revoke_share(db_session, first)
    shares.demote_if_no_active_shares(db_session, recipe)

    assert recipe.visibility == "unlisted"


def test_expired_only_share_reports_private_on_next_read(db_session, user, make_recipe):
    """SH-21 + VIS-7: expiry counts as inactive, demotion is lazy."""
    recipe = make_recipe("Ragu")
    _share(
        db_session,
        recipe,
        user,
        mode="link",
        expires_at=datetime.utcnow() - timedelta(minutes=1),
    )
    assert recipe.visibility == "unlisted"  # nothing has read it yet

    # The next authenticated read goes through the lazy evaluator.
    assert shares.effective_visibility(db_session, recipe) == "private"
    assert recipe.visibility == "private"


def test_effective_visibility_is_unchanged_while_a_share_is_active(
    db_session, user, make_recipe
):
    recipe = make_recipe("Ragu")
    _share(db_session, recipe, user, mode="link")

    assert shares.effective_visibility(db_session, recipe) == "unlisted"


def test_demote_reports_whether_it_changed_anything(db_session, user, make_recipe):
    recipe = make_recipe("Ragu")
    share, _ = _share(db_session, recipe, user, mode="link")

    assert shares.demote_if_no_active_shares(db_session, recipe) is False
    shares.revoke_share(db_session, share)
    assert shares.demote_if_no_active_shares(db_session, recipe) is True
    assert shares.demote_if_no_active_shares(db_session, recipe) is False


def test_revoke_share_keeps_the_original_revocation_timestamp(
    db_session, user, make_recipe
):
    recipe = make_recipe("Ragu")
    share, _ = _share(db_session, recipe, user, mode="link")
    first = datetime.utcnow() - timedelta(days=2)

    shares.revoke_share(db_session, share, at=first)
    shares.revoke_share(db_session, share)

    assert share.revoked_at == first


# --------------------------------------------------------------------------
# SH-25 -- recipe deletion revokes shares (guarded by crud, asserted here)
# --------------------------------------------------------------------------
def test_deleting_a_recipe_revokes_its_shares(db_session, user, make_recipe):
    recipe = make_recipe("Ragu")
    _, token = _share(db_session, recipe, user, mode="link")

    crud.revoke_shares_for_recipe(db_session, recipe.id)

    assert shares.resolve(db_session, token) is None


# --------------------------------------------------------------------------
# SWM-1 / SWM-3 / SWM-4 -- shared with me
# --------------------------------------------------------------------------
def _verified(session, user):
    user.email_verified = True
    session.flush()
    return user


def test_shared_with_me_includes_shares_naming_the_account(
    db_session, user, other_user, make_recipe
):
    _verified(db_session, other_user)
    recipe = make_recipe("Ragu")
    share, _ = _share(
        db_session, recipe, user, mode="person", recipient_user=other_user
    )

    found = shares.active_shares_for_recipient(db_session, other_user)

    assert [s.id for s in found] == [share.id]


def test_shared_with_me_matches_the_verified_email_case_insensitively(
    db_session, user, other_user, make_recipe
):
    _verified(db_session, other_user)
    recipe = make_recipe("Ragu")
    share, _ = _share(
        db_session,
        recipe,
        user,
        mode="person",
        recipient_email=other_user.email.upper(),
    )

    found = shares.active_shares_for_recipient(db_session, other_user)

    assert [s.id for s in found] == [share.id]


def test_shared_with_me_excludes_unverified_recipients(
    db_session, user, other_user, make_recipe
):
    """SWM-4: an unproven address must not grant membership."""
    other_user.email_verified = False
    db_session.flush()
    recipe = make_recipe("Ragu")
    _share(db_session, recipe, user, mode="person", recipient_email=other_user.email)

    assert shares.active_shares_for_recipient(db_session, other_user) == []


def test_shared_with_me_excludes_unverified_even_by_account_id(
    db_session, user, other_user, make_recipe
):
    other_user.email_verified = False
    db_session.flush()
    recipe = make_recipe("Ragu")
    _share(db_session, recipe, user, mode="person", recipient_user=other_user)

    assert shares.active_shares_for_recipient(db_session, other_user) == []


def test_shared_with_me_excludes_dismissed_entries(
    db_session, user, other_user, make_recipe
):
    """SWM-3: dismissal hides the entry without touching the share."""
    _verified(db_session, other_user)
    recipe = make_recipe("Ragu")
    share, token = _share(
        db_session, recipe, user, mode="person", recipient_user=other_user
    )
    share.dismissed_by_recipient_at = datetime.utcnow()
    db_session.flush()

    assert shares.active_shares_for_recipient(db_session, other_user) == []
    # The underlying share is untouched.
    assert shares.resolve(db_session, token) is not None


def test_shared_with_me_excludes_revoked_and_expired(
    db_session, user, other_user, make_recipe
):
    _verified(db_session, other_user)
    revoked, _ = _share(
        db_session,
        make_recipe("A"),
        user,
        mode="person",
        recipient_user=other_user,
    )
    shares.revoke_share(db_session, revoked)
    _share(
        db_session,
        make_recipe("B"),
        user,
        mode="person",
        recipient_user=other_user,
        expires_at=datetime.utcnow() - timedelta(seconds=1),
    )

    assert shares.active_shares_for_recipient(db_session, other_user) == []


def test_shared_with_me_excludes_other_peoples_shares(
    db_session, user, other_user, make_recipe
):
    _verified(db_session, other_user)
    recipe = make_recipe("Ragu")
    _share(db_session, recipe, user, mode="person", recipient_email="nobody@else.local")

    assert shares.active_shares_for_recipient(db_session, other_user) == []


def test_shared_with_me_includes_link_shares_addressed_to_a_person(
    db_session, user, other_user, make_recipe
):
    """SH-6: a link share may still name a recipient so it lands in the list."""
    _verified(db_session, other_user)
    recipe = make_recipe("Ragu")
    share, _ = _share(
        db_session, recipe, user, mode="link", recipient_user=other_user
    )

    assert [s.id for s in shares.active_shares_for_recipient(db_session, other_user)] == [
        share.id
    ]


# --------------------------------------------------------------------------
# Q-1 -- share_url
# --------------------------------------------------------------------------
def test_share_url_prefers_the_configured_public_base_url(monkeypatch):
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://app.example/")

    assert shares.share_url("TOKEN", _FakeRequest()) == "https://app.example/s/TOKEN"


def test_share_url_falls_back_to_the_request_base_url(monkeypatch):
    monkeypatch.delenv("PUBLIC_BASE_URL", raising=False)

    url = shares.share_url("TOKEN", _FakeRequest("https", "dev.local:8000"))

    assert url == "https://dev.local:8000/s/TOKEN"


def test_share_url_rejects_a_malformed_host_header(monkeypatch):
    """A forged ``Host`` must not be spliced into a link we hand to a user."""
    monkeypatch.delenv("PUBLIC_BASE_URL", raising=False)

    with pytest.raises(ValueError):
        shares.share_url("TOKEN", _FakeRequest("https", "evil.example/@attacker"))


def test_share_url_without_a_request_requires_configuration(monkeypatch):
    monkeypatch.delenv("PUBLIC_BASE_URL", raising=False)
    with pytest.raises(ValueError):
        shares.share_url("TOKEN", None)

    monkeypatch.setenv("PUBLIC_BASE_URL", "https://app.example")
    assert shares.share_url("TOKEN", None) == "https://app.example/s/TOKEN"


def test_share_url_percent_encodes_the_token(monkeypatch):
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://app.example")

    assert shares.share_url("a/b", None) == "https://app.example/s/a%2Fb"
