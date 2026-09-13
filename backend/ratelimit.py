"""Per-user rate limiting for the sharing endpoints (D-8).

SH-11, CP-9, and UN-7 all say *per user*. The limiter already in ``main`` is
keyed by client address (``slowapi.util.get_remote_address``), which is the
right key for ``/auth/*`` -- those calls are unauthenticated by definition, and
that is exactly where brute force and enumeration arrive.

Reusing it for the sharing routes would be wrong in both directions: several
users behind one NAT would throttle each other, and one user on many addresses
would not be throttled at all. So this module adds a *second* limiter with a
key function that prefers the authenticated subject and falls back to the
address, and leaves the existing ``/auth/*`` behaviour untouched.

Note for callers: slowapi reads the key off the request, so every limited route
must accept ``request: Request`` in its signature even when it ignores it.
"""

from __future__ import annotations

import os

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

import auth_users

__all__ = [
    "user_or_ip_key",
    "limiter",
    "SHARE_RATE_LIMIT",
    "COPY_RATE_LIMIT",
    "USERNAME_CHECK_RATE_LIMIT",
    "CATALOG_ADOPT_RATE_LIMIT",
    "CATALOG_ADMIN_RATE_LIMIT",
]

# Generous enough that nobody sharing recipes in earnest will notice, tight
# enough to cap an abuser's throughput. All three are env-overridable so a
# deployment can tighten them without a code change.
SHARE_RATE_LIMIT = os.environ.get("SHARE_RATE_LIMIT", "30/hour")
COPY_RATE_LIMIT = os.environ.get("COPY_RATE_LIMIT", "30/hour")
# Per minute rather than per hour: the registration form calls this while the
# user types, so the budget has to cover a realistic form session while still
# making handle-space enumeration impractical (UN-7).
USERNAME_CHECK_RATE_LIMIT = os.environ.get("USERNAME_CHECK_RATE_LIMIT", "30/minute")
# Catalog adoption (ADO-13). One call adopts a whole batch, so thirty an hour is
# far more than browsing the library needs.
CATALOG_ADOPT_RATE_LIMIT = os.environ.get("CATALOG_ADOPT_RATE_LIMIT", "30/hour")
# Admin catalog writes (ADM-11). Higher, because curating is many small edits.
CATALOG_ADMIN_RATE_LIMIT = os.environ.get("CATALOG_ADMIN_RATE_LIMIT", "120/hour")


def user_or_ip_key(request: Request) -> str:
    """Rate-limit key: the authenticated user when there is one, else the address.

    The bearer token is decoded rather than resolved against the database -- a
    DB round trip on every limited request would be a needless cost, and a
    signature-valid token is enough to attribute the call. A missing, malformed,
    or expired token silently falls back to the address, so an unauthenticated
    caller is still limited rather than unlimited.
    """
    header = request.headers.get("authorization") or ""
    scheme, _, token = header.partition(" ")
    if scheme.lower() == "bearer" and token:
        subject = auth_users.decode_token(token)
        if subject:
            return f"user:{subject}"
    return get_remote_address(request)


#: The second limiter. Separate instance so its counters, and any future change
#: to its storage backend, cannot affect ``/auth/*``. It honours the same
#: ``RATE_LIMIT_ENABLED=0`` switch the test suite already sets.
limiter = Limiter(
    key_func=user_or_ip_key,
    enabled=os.environ.get("RATE_LIMIT_ENABLED", "1") != "0",
)
