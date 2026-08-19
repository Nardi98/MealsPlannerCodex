"""Identity endpoints: username availability (UN-7).

Phase 0 ships this module empty and pre-wired into ``main`` (D-6) so the Phase
1A agent can fill it without touching a contended file. It owns its own
Pydantic models rather than adding them to ``schemas.py``, which is what keeps
the parallel phases from colliding.

To be built here:

* ``GET /usernames/available?u=`` -- rate-limited via ``ratelimit.limiter`` with
  ``ratelimit.USERNAME_CHECK_RATE_LIMIT``, returning ``{available, reason}`` and
  doing the same work whether the handle is taken, reserved, or free.

Deliberately *not* built here: ``POST /auth/username``. UN-8/UN-9 are deferred
to Part 2; the ``username_changed_at`` column and the ``released`` reservation
reason ship now so that flow needs no migration.
"""

from fastapi import APIRouter

router = APIRouter(tags=["usernames"])
