"""User authentication: password hashing, JWT tokens, current-user dependency.

This is the JWT/bearer-token auth for per-user accounts. It lives alongside the
older shared ``API_KEY`` gate in ``auth.py`` (kept for backward compatibility).
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext
from sqlalchemy.orm import Session

import crud
import models
from database import get_db

# JWT secret from env with a dev-only default. Override ``JWT_SECRET`` in
# production.
SECRET_KEY = os.environ.get("JWT_SECRET") or "dev-insecure-secret-change-me"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("JWT_EXPIRE_MINUTES", "10080"))

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


def hash_password(password: str) -> str:
    return _pwd_context.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return _pwd_context.verify(password, hashed)


def create_access_token(subject: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> Optional[str]:
    """Return the token subject, or ``None`` if invalid/expired."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        return None
    return payload.get("sub")


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
