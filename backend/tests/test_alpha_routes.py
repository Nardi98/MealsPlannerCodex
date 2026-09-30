"""ALPHA-GATE: the admin invite routes (spec 2026-09-30-alpha-allowlist-design).

Temporary scaffolding, deleted whole when the alpha ends. The marker test at the
bottom is what makes that deletion mechanical rather than archaeological.

Modelled on ``test_catalog_admin.py``'s route sweeps: the router table is built
from the router itself and compared against the frozen contract, so a fifth
route cannot appear without a test noticing.
"""

from pathlib import Path

import re

import pytest
from sqlalchemy import func, select

import alpha
import alpha_routes
import auth_users
import crud
import models
from main import app
from tests.conftest import client_as, db_client

BACKEND_ROOT = Path(__file__).resolve().parent.parent

INVITE_KEYS = {"id", "email", "note", "created_at", "signed_up", "signed_up_at"}
MISSING_ID = 10**9

#: The Contracts' route table, exactly (plan "HTTP — backend/alpha_routes.py").
CONTRACT_ROUTES = {
    ("GET", "/admin/alpha/invites"),
    ("POST", "/admin/alpha/invites"),
    ("PATCH", "/admin/alpha/invites/{invite_id}"),
    ("DELETE", "/admin/alpha/invites/{invite_id}"),
}


def _router_table():
    return sorted(
        (method, route.path)
        for route in alpha_routes.router.routes
        for method in route.methods
    )


ROUTER_TABLE = _router_table()


@pytest.fixture
def admin(db_session, admin_user):
    try:
        yield client_as(db_session, admin_user)
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def make_invite(db_session):
    def _make(email, note=None, invited_by=None):
        invite = models.AlphaInvite(
            email=email, note=note, invited_by_user_id=invited_by
        )
        db_session.add(invite)
        db_session.flush()
        return invite

    return _make


def _body_for(method):
    """A body the route would accept, so validation is never what answers."""
    if method == "POST":
        return {"emails": "sweep@example.com"}
    if method == "PATCH":
        return {"note": "sweep"}
    return None


def _call(client, method, path, invite_id):
    return client.request(
        method,
        path.replace("{invite_id}", str(invite_id)),
        json=_body_for(method),
    )


def _invite_count(session):
    return session.scalar(select(func.count()).select_from(models.AlphaInvite))


# --- Route table and guards ---------------------------------------------------


def test_the_router_serves_exactly_the_contract_routes():
    assert set(ROUTER_TABLE) == CONTRACT_ROUTES


def test_the_router_depends_on_require_admin():
    assert any(
        dep.dependency is auth_users.require_admin
        for dep in alpha_routes.router.dependencies
    )


@pytest.mark.parametrize(("method", "path"), ROUTER_TABLE)
def test_every_route_is_401_for_anonymous_callers(
    db_session, make_invite, method, path
):
    invite = make_invite("guarded@example.com")
    try:
        response = _call(db_client(db_session), method, path, invite.id)
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}


@pytest.mark.parametrize(("method", "path"), ROUTER_TABLE)
def test_every_route_is_one_identical_403_for_a_non_admin(
    db_session, user, make_invite, method, path
):
    """The same bytes whether the invite exists or not: no enumeration."""
    invite = make_invite("guarded@example.com")
    client = client_as(db_session, user)
    try:
        existing = _call(client, method, path, invite.id)
        missing = _call(client, method, path, MISSING_ID)
    finally:
        app.dependency_overrides.clear()

    assert existing.status_code == missing.status_code == 403
    assert existing.json() == {"detail": "Forbidden"}
    assert existing.content == missing.content
    assert existing.headers.get("content-type") == missing.headers.get("content-type")


# --- GET ----------------------------------------------------------------------


def test_get_lists_invites_newest_first(admin, make_invite):
    make_invite("older@example.com")
    make_invite("newer@example.com")

    response = admin.get("/admin/alpha/invites")

    assert response.status_code == 200, response.text
    assert [row["email"] for row in response.json()] == [
        "newer@example.com",
        "older@example.com",
    ]


def test_get_exposes_exactly_the_contract_fields_and_never_the_inviter(
    admin, admin_user, make_invite
):
    make_invite("listed@example.com", note="a friend", invited_by=admin_user.id)

    row = admin.get("/admin/alpha/invites").json()[0]

    assert set(row) == INVITE_KEYS
    assert row["note"] == "a friend"


def test_get_reports_signed_up_with_the_accounts_created_at(
    admin, db_session, make_invite
):
    account = crud.create_user(
        db_session,
        email="joined@example.com",
        username="joined",
        hashed_password="x",
    )
    db_session.flush()
    make_invite("joined@example.com")
    make_invite("pending@example.com")

    rows = {row["email"]: row for row in admin.get("/admin/alpha/invites").json()}

    assert rows["joined@example.com"]["signed_up"] is True
    assert rows["joined@example.com"]["signed_up_at"].startswith(
        account.created_at.isoformat()[:19]
    )
    assert rows["pending@example.com"]["signed_up"] is False
    assert rows["pending@example.com"]["signed_up_at"] is None


# --- POST ---------------------------------------------------------------------


def test_post_partitions_added_duplicates_and_invalid(admin, make_invite):
    make_invite("dupe@example.com")

    response = admin.post(
        "/admin/alpha/invites",
        json={"emails": "new@example.com, dupe@example.com\ngarbage"},
    )

    assert response.status_code == 200, response.text
    assert response.json() == {
        "added": ["new@example.com"],
        "skipped_duplicates": ["dupe@example.com"],
        "invalid": ["garbage"],
    }


def test_posting_the_same_batch_twice_adds_nothing_the_second_time(
    admin, db_session
):
    body = {"emails": "again@example.com"}
    admin.post("/admin/alpha/invites", json=body)
    before = _invite_count(db_session)

    response = admin.post("/admin/alpha/invites", json=body)

    assert response.json() == {
        "added": [],
        "skipped_duplicates": ["again@example.com"],
        "invalid": [],
    }
    assert _invite_count(db_session) == before


def test_post_records_the_admin_as_the_inviter(admin, admin_user, db_session):
    admin.post("/admin/alpha/invites", json={"emails": "who@example.com"})

    invite = db_session.scalar(
        select(models.AlphaInvite).where(
            models.AlphaInvite.email == "who@example.com"
        )
    )
    assert invite.invited_by_user_id == admin_user.id


def test_post_with_an_empty_string_is_three_empty_lists(admin, db_session):
    response = admin.post("/admin/alpha/invites", json={"emails": ""})

    assert response.status_code == 200, response.text
    assert response.json() == {"added": [], "skipped_duplicates": [], "invalid": []}
    assert _invite_count(db_session) == 0


def test_post_rejects_a_non_string_emails_field(admin):
    assert admin.post("/admin/alpha/invites", json={"emails": 1}).status_code == 422


def test_post_rejects_an_unknown_field(admin):
    response = admin.post(
        "/admin/alpha/invites", json={"emails": "a@example.com", "note": "x"}
    )

    assert response.status_code == 422


# --- PATCH --------------------------------------------------------------------


def test_patch_sets_the_note_and_returns_the_row(admin, make_invite):
    invite = make_invite("noted@example.com")

    response = admin.patch(
        f"/admin/alpha/invites/{invite.id}", json={"note": "  beta tester  "}
    )

    assert response.status_code == 200, response.text
    assert set(response.json()) == INVITE_KEYS
    assert response.json()["note"] == "beta tester"
    assert response.json()["email"] == "noted@example.com"


def test_patch_with_null_clears_the_note(admin, make_invite):
    invite = make_invite("noted@example.com", note="old")

    response = admin.patch(f"/admin/alpha/invites/{invite.id}", json={"note": None})

    assert response.status_code == 200, response.text
    assert response.json()["note"] is None


def test_patch_refuses_a_body_carrying_an_email(admin, make_invite):
    invite = make_invite("noted@example.com")

    response = admin.patch(
        f"/admin/alpha/invites/{invite.id}",
        json={"note": "x", "email": "hijack@example.com"},
    )

    assert response.status_code == 422


def test_patch_on_a_missing_invite_is_404(admin):
    response = admin.patch(f"/admin/alpha/invites/{MISSING_ID}", json={"note": "x"})

    assert response.status_code == 404
    assert response.json() == {"detail": "Invite not found"}


# --- DELETE -------------------------------------------------------------------


def test_delete_removes_the_invite_with_an_empty_204(admin, db_session, make_invite):
    invite = make_invite("gone@example.com")

    response = admin.delete(f"/admin/alpha/invites/{invite.id}")

    assert response.status_code == 204
    assert response.content == b""
    assert db_session.get(models.AlphaInvite, invite.id) is None


def test_delete_on_a_missing_invite_is_404(admin):
    response = admin.delete(f"/admin/alpha/invites/{MISSING_ID}")

    assert response.status_code == 404
    assert response.json() == {"detail": "Invite not found"}


def test_deleting_an_invite_leaves_an_existing_account_intact(
    admin, db_session, make_invite
):
    """Withdrawing an invite is not a way to delete somebody's account."""
    account = crud.create_user(
        db_session,
        email="joined@example.com",
        username="joined",
        hashed_password="x",
    )
    db_session.flush()
    invite = make_invite("joined@example.com")

    assert admin.delete(f"/admin/alpha/invites/{invite.id}").status_code == 204
    assert db_session.get(models.User, account.id) is not None


# --- Removal marker -----------------------------------------------------------


ALPHA_SOURCES = [
    "alpha.py",
    "alpha_routes.py",
    "tests/test_alpha.py",
    "tests/test_alpha_routes.py",
    "tests/test_alpha_gate.py",
]


def test_every_alpha_line_in_main_is_marked_for_removal():
    """The removal checklist, enforced as a property rather than a count.

    Deleting the alpha means deleting every ``main.py`` line that mentions it,
    and ``git grep ALPHA-GATE`` is how the deleter finds them -- so a line that
    names ``alpha`` without the marker is a line the checklist would leave
    behind. Counting markers alone once let the two imports slip through: they
    were unmarked, so the grep pointed at three lines while removal needed
    five. Asserting the property instead cannot drift that way.
    """
    text = (BACKEND_ROOT / "main.py").read_text(encoding="utf-8")

    mentions = [
        line
        for line in text.splitlines()
        if re.search(r"\balpha\b|\balpha_routes\b", line)
    ]
    unmarked = [line for line in mentions if "ALPHA-GATE" not in line]

    assert unmarked == [], unmarked
    # Six: two imports, the router, one guard per signup path, and the comment
    # explaining the ordering of the register guard. A seventh means a hook the
    # spec does not know about; fewer means one was lost.
    assert len(mentions) == 6, mentions


@pytest.mark.parametrize("source", ALPHA_SOURCES)
def test_every_alpha_source_announces_itself_in_its_first_lines(source):
    head = (BACKEND_ROOT / source).read_text(encoding="utf-8").splitlines()[:20]

    assert any("ALPHA-GATE" in line for line in head)


def test_the_detail_sentence_is_the_one_the_spec_froze():
    assert alpha.NOT_INVITED_DETAIL == (
        "Meal Planner is in a closed alpha. "
        "This email address hasn't been invited yet."
    )
