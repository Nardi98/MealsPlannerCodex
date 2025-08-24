"""Migration script to normalise existing season_months values.

Existing installations stored seasonality as free form strings.  This script
extracts any month numbers (1-12) and rewrites the field using the new
comma-separated representation expected by the application.
"""
from __future__ import annotations

import re
from sqlalchemy import select

from database import SessionLocal
from models import Ingredient


def migrate() -> None:
    """Convert free-text ``season_months`` into normalised comma-separated values."""

    with SessionLocal() as session:
        ingredients = session.execute(select(Ingredient)).scalars().all()
        for ing in ingredients:
            raw = getattr(ing, "_season_months", None)
            if not raw:
                continue
            months = [int(m) for m in re.findall(r"\b(?:1[0-2]|[1-9])\b", raw)]
            ing.season_months = months
        session.commit()


if __name__ == "__main__":
    migrate()
