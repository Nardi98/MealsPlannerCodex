"""Outbound transactional email (verification + password reset).

The backend is chosen at call time from the ``MAIL_BACKEND`` environment
variable:

* ``console`` (default) -- log the message to stdout and append it to
  :data:`outbox`. Zero configuration; used in local development and by the test
  suite, which reads :data:`outbox` to recover the token it just triggered.
* ``smtp`` -- send via an SMTP server described by ``SMTP_HOST`` / ``SMTP_PORT``
  / ``SMTP_USER`` / ``SMTP_PASSWORD`` / ``SMTP_FROM``.

Keeping this behind one ``send_email`` call means the auth routes never care
which backend is live.
"""
from __future__ import annotations

import os
import smtplib
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


def send_email(*, to: str, subject: str, body: str) -> None:
    """Dispatch an email via the backend named by ``MAIL_BACKEND``."""
    message = SentMessage(to=to, subject=subject, body=body)
    backend = os.environ.get("MAIL_BACKEND", "console").lower()
    if backend == "smtp":
        _send_smtp(message)
    else:
        _send_console(message)
