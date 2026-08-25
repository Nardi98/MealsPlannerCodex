"""The Resend HTTPS backend.

Railway blocks outbound SMTP (ports 25/465/587) to prevent spam abuse, so
``MAIL_BACKEND=smtp`` cannot work there -- the connection to smtp.resend.com
simply times out and registration 500s. Resend's REST API is ordinary HTTPS on
443, which is not blocked, so that is the transport the deployment uses.
"""

import json

import httpx
import pytest

import mailer


@pytest.fixture(autouse=True)
def _resend_env(monkeypatch):
    monkeypatch.setenv("MAIL_BACKEND", "resend")
    monkeypatch.setenv("RESEND_API_KEY", "re_test_key")
    monkeypatch.setenv("MAIL_FROM", "noreply@example.com")
    mailer.outbox.clear()
    yield
    mailer.outbox.clear()


def _capture(monkeypatch, response=None):
    """Swap httpx.post for a recorder, returning the list it records into."""
    calls = []

    def _post(url, **kwargs):
        calls.append({"url": url, **kwargs})
        return response or httpx.Response(
            200, json={"id": "abc-123"}, request=httpx.Request("POST", url)
        )

    monkeypatch.setattr(mailer.httpx, "post", _post)
    return calls


def test_it_posts_the_message_to_the_resend_api(monkeypatch):
    calls = _capture(monkeypatch)

    mailer.send_email(to="someone@example.com", subject="Verify", body="link here")

    assert len(calls) == 1
    call = calls[0]
    assert call["url"] == "https://api.resend.com/emails"
    assert call["headers"]["Authorization"] == "Bearer re_test_key"
    payload = call["json"]
    assert payload["from"] == "noreply@example.com"
    assert payload["to"] == ["someone@example.com"]
    assert payload["subject"] == "Verify"
    assert payload["text"] == "link here"


def test_it_sets_a_timeout(monkeypatch):
    """A hung mail provider must not hold a request thread open indefinitely."""
    calls = _capture(monkeypatch)

    mailer.send_email(to="a@example.com", subject="s", body="b")

    assert calls[0]["timeout"] > 0


def test_a_rejected_send_raises_with_the_provider_reason(monkeypatch):
    """A silent failure here means a user never gets their verification link."""
    rejection = httpx.Response(
        422,
        json={"message": "The from address is not verified"},
        request=httpx.Request("POST", "https://api.resend.com/emails"),
    )
    _capture(monkeypatch, response=rejection)

    with pytest.raises(RuntimeError, match="not verified"):
        mailer.send_email(to="a@example.com", subject="s", body="b")


def test_a_missing_api_key_fails_loudly(monkeypatch):
    monkeypatch.delenv("RESEND_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="RESEND_API_KEY"):
        mailer.send_email(to="a@example.com", subject="s", body="b")


def test_the_resend_backend_does_not_populate_the_outbox(monkeypatch):
    """``outbox`` is the console backend's test seam, not a send log."""
    _capture(monkeypatch)

    mailer.send_email(to="a@example.com", subject="s", body="b")

    assert mailer.outbox == []


def test_console_remains_the_default(monkeypatch):
    monkeypatch.delenv("MAIL_BACKEND", raising=False)

    mailer.send_email(to="a@example.com", subject="s", body="b")

    assert [m.to for m in mailer.outbox] == ["a@example.com"]
