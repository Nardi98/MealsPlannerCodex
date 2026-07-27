"""User authentication: password hashing, JWT tokens, current-user dependency.

The app's only authentication mechanism. Every route touching user-owned data
depends on :func:`get_current_user` (as ``main.CurrentUser``) and scopes its
queries to that user's id.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import uuid4

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext
from pydantic import BaseModel
from sqlalchemy.orm import Session

import crud
import models
import schemas
from database import get_db


def resolve_jwt_secret() -> str:
    """Resolve the JWT signing secret from the environment, failing closed.

    Mirrors :func:`database.resolve_database_url`: a missing ``JWT_SECRET`` is a
    deployment error, not something to paper over with a shared default that
    would let anyone forge tokens. A throwaway dev default is only handed out
    when ``AUTH_DEV_MODE`` is explicitly enabled.
    """
    secret = os.environ.get("JWT_SECRET")
    if secret:
        return secret
    if os.environ.get("AUTH_DEV_MODE") == "1":
        return "dev-insecure-secret-change-me"
    raise RuntimeError(
        "JWT_SECRET must be set to a strong random string "
        "(set AUTH_DEV_MODE=1 to allow an insecure dev-only default)"
    )


SECRET_KEY = resolve_jwt_secret()
ALGORITHM = "HS256"
# Short-lived access token; the refresh cookie carries the long-lived session.
ACCESS_TOKEN_EXPIRE_MINUTES = int(
    os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", "15")
)
REFRESH_TOKEN_EXPIRE_DAYS = int(os.environ.get("REFRESH_TOKEN_EXPIRE_DAYS", "30"))
# Email verification / password reset links are short-lived signed tokens.
VERIFY_TOKEN_EXPIRE_MINUTES = int(
    os.environ.get("VERIFY_TOKEN_EXPIRE_MINUTES", str(60 * 24))
)
RESET_TOKEN_EXPIRE_MINUTES = int(
    os.environ.get("RESET_TOKEN_EXPIRE_MINUTES", "60")
)

MIN_PASSWORD_LENGTH = 8

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# A precomputed hash of a throwaway password. Login runs ``verify_password``
# against this on the no-such-user path so that a missing account costs the same
# wall-clock time as a wrong password, closing the account-enumeration timing
# oracle.
DUMMY_PASSWORD_HASH = _pwd_context.hash("dummy-password-for-timing")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


# --- request/response schemas ----------------------------------------------
# NOTE: these mirror the auth contract that would normally live in
# ``schemas.py`` (owned by another agent). They are defined here to avoid
# editing that file; the reusable ``UserCreate`` / ``LoginRequest`` /
# ``GoogleLoginRequest`` / ``Token`` schemas are imported from ``schemas``.


class UserOut(schemas.UserOut):
    """``schemas.UserOut`` plus the account's email-verification state."""

    email_verified: bool = False


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


class VerifyEmailRequest(BaseModel):
    token: str


def validate_password(password: str) -> str:
    """Return ``password`` if it meets policy, else raise ``ValueError``."""
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(
            f"Password must be at least {MIN_PASSWORD_LENGTH} characters"
        )
    return password


def hash_password(password: str) -> str:
    return _pwd_context.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return _pwd_context.verify(password, hashed)


def _encode(subject: str, token_type: str, expires_at: datetime, jti: str) -> str:
    """Sign a JWT carrying our standard ``sub``/``type``/``iat``/``exp``/``jti``."""
    payload = {
        "sub": subject,
        "type": token_type,
        "iat": datetime.now(timezone.utc),
        "exp": expires_at,
        "jti": jti,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def create_access_token(subject: str) -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES
    )
    return _encode(subject, "access", expires_at, uuid4().hex)


def create_refresh_token(subject: str) -> tuple[str, str, datetime]:
    """Return ``(token, jti, expires_at)`` for a new refresh token.

    ``expires_at`` is a naive UTC datetime to match the DB column the caller
    stores it in.
    """
    expires_at = datetime.now(timezone.utc) + timedelta(
        days=REFRESH_TOKEN_EXPIRE_DAYS
    )
    jti = uuid4().hex
    token = _encode(subject, "refresh", expires_at, jti)
    return token, jti, expires_at.replace(tzinfo=None)


def create_email_token(subject: str, token_type: str, expires_minutes: int) -> str:
    """Sign a short-lived token for ``verify`` / ``reset`` email flows."""
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)
    return _encode(subject, token_type, expires_at, uuid4().hex)


def _decode(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        return None


def decode_token(token: str) -> Optional[str]:
    """Return the subject of a valid access token, else ``None``.

    Refresh / verify / reset tokens are rejected here: an access token is the
    only thing that authorises a request.
    """
    payload = _decode(token)
    if payload is None:
        return None
    # ``type`` is absent on nothing we issue now, but tolerate its absence so a
    # token minted before the claim existed still authenticates.
    if payload.get("type", "access") != "access":
        return None
    return payload.get("sub")


def decode_refresh_token(token: str) -> Optional[dict]:
    """Return the payload of a valid refresh token, else ``None``."""
    payload = _decode(token)
    if payload is None or payload.get("type") != "refresh":
        return None
    return payload


def decode_email_token(token: str, expected_type: str) -> Optional[str]:
    """Return the subject of a valid ``expected_type`` token, else ``None``."""
    payload = _decode(token)
    if payload is None or payload.get("type") != expected_type:
        return None
    return payload.get("sub")


_google_request = None


def _google_transport():
    """A reused HTTP transport for Google's cert endpoint.

    Verification refetches Google's signing certs; a shared session keeps the
    connection pooled instead of a fresh TLS handshake on every sign-in.
    """
    global _google_request
    if _google_request is None:
        # Imported lazily so the rest of auth works without the Google deps
        # installed, and so startup does not pay for them.
        from google.auth.transport import requests as google_requests

        _google_request = google_requests.Request()
    return _google_request


def verify_google_token(credential: str) -> dict:
    """Verify a Google ID token and return its claims.

    Raises ``ValueError`` if ``GOOGLE_CLIENT_ID`` is unset or the token is not a
    valid, unexpired token issued to this app.
    """
    client_id = os.environ.get("GOOGLE_CLIENT_ID")
    if not client_id:
        raise ValueError("GOOGLE_CLIENT_ID is not configured")
    from google.oauth2 import id_token as google_id_token

    return google_id_token.verify_oauth2_token(
        credential, _google_transport(), client_id
    )


def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> models.User:
    """FastAPI dependency resolving the bearer token to a ``User`` (401 if not)."""
    credentials_error = HTTPException(
        status_code=401, detail="Not authenticated"
    )
    if not token:
        raise credentials_error
    subject = decode_token(token)
    if subject is None:
        raise credentials_error
    try:
        user_id = int(subject)
    except (TypeError, ValueError):
        raise credentials_error
    user = crud.get_user(db, user_id)
    if user is None:
        raise credentials_error
    return user
