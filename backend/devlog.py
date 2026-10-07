"""The developer log: a generic, per-user event trace for debugging.

Any area of the app may write to it under its own ``channel`` (``planner``
first). The app never reads it back to make a decision -- it exists so a
developer can export one user's log and see *why* something happened. Only the
admin Logs routes read it.

``record`` never commits: the caller owns the transaction, so an event is
stored exactly when the change it describes is. Each write prunes the writer's
rows older than :data:`RETENTION_DAYS`, which keeps storage bounded without a
scheduled job.

A leaf module: it imports nothing of ours but ``models`` and ``scoping``.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from models import DevLogEntry
from scoping import scope

__all__ = ["RETENTION_DAYS", "record", "export"]

RETENTION_DAYS = 90


def _json_safe(payload: Any) -> Any:
    """``payload`` with dates and other non-JSON values turned into strings."""
    return json.loads(json.dumps(payload, default=str))


def record(
    session: Session, *, user_id: int, channel: str, event: str, payload: Dict[str, Any]
) -> DevLogEntry:
    """Add one entry for ``user_id`` and prune that user's expired rows. Flushes only."""
    cutoff = datetime.utcnow() - timedelta(days=RETENTION_DAYS)
    session.execute(
        scope(delete(DevLogEntry), DevLogEntry.user_id, user_id).where(
            DevLogEntry.created_at < cutoff
        ),
        execution_options={"synchronize_session": False},
    )
    entry = DevLogEntry(
        user_id=user_id, channel=channel, event=event, payload=_json_safe(payload)
    )
    session.add(entry)
    session.flush()
    return entry


def export(
    session: Session, *, user_id: int, channel: Optional[str] = None
) -> List[Dict[str, Any]]:
    """``user_id``'s entries, oldest first, optionally limited to one ``channel``."""
    stmt = scope(select(DevLogEntry), DevLogEntry.user_id, user_id)
    if channel:
        stmt = stmt.where(DevLogEntry.channel == channel)
    stmt = stmt.order_by(DevLogEntry.created_at, DevLogEntry.id)
    return [
        {
            "id": e.id,
            "created_at": e.created_at.isoformat(),
            "channel": e.channel,
            "event": e.event,
            "payload": e.payload,
        }
        for e in session.execute(stmt).scalars()
    ]
