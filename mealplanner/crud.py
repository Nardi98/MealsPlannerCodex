"""CRUD operations for the Meals Planner Codex application."""

from __future__ import annotations

from typing import Dict, Iterable, List, Any


def get_recipes() -> List[str]:
    """Return a list of recipe names.

    This function is a placeholder that represents fetching recipe data from
    a database or external service. It is intentionally left unimplemented so
    that tests can mock it to provide deterministic data.
    """
    raise NotImplementedError("Database access not implemented")


def get_plan() -> Dict[str, List[str]]:
    """Return the current meal plan."""
    raise NotImplementedError("Plan retrieval not implemented")


def import_data(file_obj: Any) -> None:
    """Import data from the given uploaded file object."""
    raise NotImplementedError("Import not implemented")


def export_data() -> str:
    """Export application data and return a serialized representation."""
    raise NotImplementedError("Export not implemented")
