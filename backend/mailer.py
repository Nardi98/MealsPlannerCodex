"""Outbound transactional email (verification + password reset).

The backend is chosen at call time from the ``MAIL_BACKEND`` environment
variable:

* ``console`` (default) -- log the message to stdout and append it to
  :data:`outbox`. Zero configuration; used in local development and by the test
  suite, which reads :data:`outbox` to recover the token it just triggered.
* ``resend`` -- POST to Resend's HTTPS API using ``RESEND_API_KEY`` and
  ``MAIL_FROM``. This is what the deployment uses: Railway blocks outbound SMTP
  (ports 25/465/587) to prevent spam abuse, so ``smtp`` cannot reach a provider
  from there at all -- the connection times out and registration 500s. Ordinary
  HTTPS on 443 is not blocked.
* ``smtp`` -- send via an SMTP server described by ``SMTP_HOST`` / ``SMTP_PORT``
  / ``SMTP_USER`` / ``SMTP_PASSWORD`` / ``SMTP_FROM``. Kept for environments
  that permit outbound SMTP.

Keeping this behind one ``send_email`` call means the auth routes never care
which backend is live.
"""
from __future__ import annotations

import os
import smtplib

import httpx
from dataclasses import dataclass
from email.message import EmailMessage
from typing import List


@dataclass(frozen=True)
class SentMessage:
    """A record of one dispatched email, for the console backend / tests."""

    to: str
    subject: str
    body: str


#: In-memory record of messages the ``console`` backend "sent". Development and
#: tests inspect this to recover the link/token that was mailed. Never populated
#: by the ``smtp`` backend.
outbox: List[SentMessage] = []


def _send_console(message: SentMessage) -> None:
    outbox.append(message)
    print(
        f"[mailer:console] To: {message.to}\n"
        f"Subject: {message.subject}\n\n{message.body}\n"
    )


def _send_smtp(message: SentMessage) -> None:
    host = os.environ.get("SMTP_HOST")
    if not host:
        raise RuntimeError("MAIL_BACKEND=smtp requires SMTP_HOST to be set")
    port = int(os.environ.get("SMTP_PORT", "587"))
    user = os.environ.get("SMTP_USER")
    password = os.environ.get("SMTP_PASSWORD")
    sender = os.environ.get("SMTP_FROM", user or "no-reply@mealplanner.local")

    email = EmailMessage()
    email["From"] = sender
    email["To"] = message.to
    email["Subject"] = message.subject
    email.set_content(message.body)

    with smtplib.SMTP(host, port) as server:
        server.starttls()
        if user and password:
            server.login(user, password)
        server.send_message(email)


RESEND_ENDPOINT = "https://api.resend.com/emails"

#: A mail provider that stops responding must not hold a request thread open
#: indefinitely -- registration would hang rather than fail.
RESEND_TIMEOUT_SECONDS = 10.0


def _send_resend(message: SentMessage) -> None:
    api_key = os.environ.get("RESEND_API_KEY")
    if not api_key:
        raise RuntimeError("MAIL_BACKEND=resend requires RESEND_API_KEY to be set")
    sender = os.environ.get("MAIL_FROM") or os.environ.get("SMTP_FROM")
    if not sender:
        raise RuntimeError("MAIL_BACKEND=resend requires MAIL_FROM to be set")

    response = httpx.post(
        RESEND_ENDPOINT,
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "from": sender,
            "to": [message.to],
            "subject": message.subject,
            "text": message.body,
        },
        timeout=RESEND_TIMEOUT_SECONDS,
    )
    if response.status_code >= 400:
        # Surface the provider's own reason. The failures here are configuration
        # ones -- an unverified sender domain, a revoked key -- and the reason is
        # the whole diagnosis; without it this is an opaque 500 on registration.
        try:
            reason = response.json().get("message", response.text)
        except ValueError:
            reason = response.text
        raise RuntimeError(f"Resend rejected the message ({response.status_code}): {reason}")


def send_email(*, to: str, subject: str, body: str) -> None:
    """Dispatch an email via the backend named by ``MAIL_BACKEND``."""
    message = SentMessage(to=to, subject=subject, body=body)
    backend = os.environ.get("MAIL_BACKEND", "console").lower()
    if backend == "resend":
        _send_resend(message)
    elif backend == "smtp":
        _send_smtp(message)
    else:
        _send_console(message)
