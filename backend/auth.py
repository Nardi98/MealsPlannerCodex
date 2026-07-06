"""API-key authentication for mutating routes.

When the ``API_KEY`` environment variable is set, requests to protected routes
must send a matching ``X-API-Key`` header. When it is unset, auth is disabled so
local development and the existing test suite keep working without configuration.
"""
from __future__ import annotations

import os

from fastapi import Header, HTTPException


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    """FastAPI dependency enforcing the ``X-API-Key`` header when configured."""
    expected = os.environ.get("API_KEY")
    if not expected:
        return
    if x_api_key != expected:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
