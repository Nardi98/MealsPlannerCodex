"""The refresh cookie's cross-site attributes.

The SPA and the API are deployed as two Railway services on two different
registrable domains, so ``/auth/refresh`` is a cross-site XHR. A ``SameSite=Lax``
cookie is not sent on it, which would silently end every session on page reload.
``COOKIE_SAMESITE`` exists to turn that into ``None`` in a deployment while
leaving local development -- same-origin, over http -- on the safer ``Lax``.
"""

import pytest

import crud
import main
from conftest import db_client


@pytest.fixture
def client(db_session):
    try:
        yield db_client(db_session)
    finally:
        main.app.dependency_overrides.clear()


def _login(client, db_session, email="cookie@x.com"):
    client.post(
        "/auth/register", json={"email": email, "password": "Pw123456", "display_name": None}
    )
    user = crud.get_user_by_email(db_session, email)
    crud.set_email_verified(db_session, user, True)
    db_session.commit()
    return client.post("/auth/login", json={"email": email, "password": "Pw123456"})


def _set_cookie_header(response):
    return response.headers["set-cookie"].lower()


def test_default_is_lax_and_insecure(client, db_session, monkeypatch):
    """Unset environment must behave exactly as it did before this knob existed."""
    monkeypatch.delenv("COOKIE_SAMESITE", raising=False)
    monkeypatch.delenv("COOKIE_SECURE", raising=False)

    header = _set_cookie_header(_login(client, db_session))

    assert "samesite=lax" in header
    assert "secure" not in header
    assert "httponly" in header


def test_none_and_secure_are_emitted_for_the_cross_site_deployment(
    client, db_session, monkeypatch
):
    monkeypatch.setenv("COOKIE_SAMESITE", "none")
    monkeypatch.setenv("COOKIE_SECURE", "1")

    header = _set_cookie_header(_login(client, db_session))

    assert "samesite=none" in header
    assert "secure" in header


def test_logout_clears_with_matching_attributes(client, db_session, monkeypatch):
    """``delete_cookie`` must mirror ``set_cookie``.

    A clear whose SameSite/Secure differ from the original is ignored by some
    browsers, leaving a logged-out user holding a live refresh cookie.
    """
    monkeypatch.setenv("COOKIE_SAMESITE", "none")
    monkeypatch.setenv("COOKIE_SECURE", "1")
    token = _login(client, db_session).cookies["refresh_token"]

    resp = client.post("/auth/logout", cookies={"refresh_token": token})

    header = _set_cookie_header(resp)
    assert "samesite=none" in header
    assert "secure" in header


def test_samesite_none_without_secure_is_refused(monkeypatch):
    """Browsers drop such a cookie silently; fail loudly instead."""
    monkeypatch.setenv("COOKIE_SAMESITE", "none")
    monkeypatch.setenv("COOKIE_SECURE", "0")

    with pytest.raises(RuntimeError, match="COOKIE_SECURE"):
        main.cookie_policy()


@pytest.mark.parametrize("value", ["strict", "Lax", "NONE"])
def test_recognised_values_are_case_insensitive(monkeypatch, value):
    monkeypatch.setenv("COOKIE_SAMESITE", value)
    monkeypatch.setenv("COOKIE_SECURE", "1")

    assert main.cookie_policy().samesite == value.lower()


def test_an_unrecognised_samesite_is_refused(monkeypatch):
    monkeypatch.setenv("COOKIE_SAMESITE", "sometimes")

    with pytest.raises(RuntimeError, match="COOKIE_SAMESITE"):
        main.cookie_policy()
