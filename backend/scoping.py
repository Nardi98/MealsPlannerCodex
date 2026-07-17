"""Ownership scoping shared by ``crud`` and the ``mealplanner`` package.

Every per-user resource is filtered through :func:`scope` (queries) or
:func:`owned` (loaded objects), so "was this scoped?" is answerable by grep
rather than by reading each query.

``user_id=None`` means *no scoping* — used by lower-level tests that operate on
a single unowned dataset. It is a deliberate opt-out, not a default to rely on
in request paths: routes always pass ``current_user.id``.
"""

from __future__ import annotations

from typing import Any

__all__ = ["scope", "owned"]


def scope(query, column, user_id: int | None):
    """Filter ``query`` to ``column == user_id`` unless ``user_id`` is ``None``.

    Works for both ``select()`` constructs and legacy ORM ``Query`` objects:
    ``Query.where`` is a synonym for ``Query.filter``.
    """

    return query if user_id is None else query.where(column == user_id)


def owned(obj: Any, user_id: int | None) -> bool:
    """Return whether ``obj`` may be accessed by ``user_id``.

    The object-side counterpart of :func:`scope`: ``None`` applies no scoping,
    otherwise the object's ``user_id`` must match so cross-user access is
    denied.
    """

    return obj is not None and (user_id is None or obj.user_id == user_id)
