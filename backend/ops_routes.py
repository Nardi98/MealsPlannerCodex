"""Platform operations endpoints.

Its own module rather than another block in ``main.py``, for the reason
CLAUDE.md gives for ``username_routes`` / ``share_routes`` / ``public_pages``:
routes that belong to one concern live together, and work on them does not
serialise on the shared file. This concern is "things the platform talks to",
which is not a domain and has no business sitting among the recipe handlers.
"""
from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    """Liveness probe for the platform healthcheck.

    Deliberately does not touch the database. A probe that fails whenever the
    database blinks hands the platform a reason to kill an otherwise healthy
    container, turning a brief upstream hiccup into a restart loop. Whether the
    database is reachable belongs in monitoring, not in liveness.
    """
    return {"status": "ok"}
