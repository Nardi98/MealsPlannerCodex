"""Database utilities for the Meals Planner Codex application."""

from __future__ import annotations

from pathlib import Path

import sqlalchemy as sa
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# SQLAlchemy database URL for the application. Uses a SQLite file stored under
# the backend's ``data`` directory.  Build an absolute path so tests and the
# app behave the same regardless of the current working directory.
_BASE_DIR = Path(__file__).resolve().parent
DATABASE_URL = f"sqlite:///{_BASE_DIR / 'data' / 'app.db'}"

# Create the core SQLAlchemy engine and session factory. ``future=True`` enables
# 2.0 style usage which is what this project is targeting.
engine = create_engine(DATABASE_URL, future=True)

SessionLocal = sessionmaker(
    bind=engine, autoflush=False, autocommit=False, future=True
)

# Base class for declarative models. All ORM models in the project should
# inherit from this ``Base`` so that ``Base.metadata`` contains all tables.
Base = declarative_base()


def _migrate_plan_date_pk(conn: sa.Connection) -> None:
    """Upgrade older schemas lacking ``meal_slots.plan_date``.

    Earlier versions keyed ``MealSlot`` rows by ``meal_plan_id``.  This helper
    converts those databases to use ``plan_date`` as the foreign key and primary
    key for ``meal_plans``.  It is safe to call multiple times; if the new
    schema is already in place the function performs no action.
    """

    insp = sa.inspect(conn)
    slot_cols = {col["name"] for col in insp.get_columns("meal_slots")}
    if "plan_date" in slot_cols:
        return  # already migrated

    # Rebuild ``meal_plans`` with ``plan_date`` as the primary key.
    conn.execute(
        sa.text(
            """
            CREATE TABLE meal_plans_new (
                plan_date DATE NOT NULL PRIMARY KEY
            )
            """
        )
    )
    conn.execute(
        sa.text(
            "INSERT INTO meal_plans_new(plan_date) SELECT plan_date FROM meal_plans GROUP BY plan_date"
        )
    )

    # Rebuild ``meal_slots`` to reference ``plan_date`` directly.
    conn.execute(
        sa.text(
            """
            CREATE TABLE meal_slots_new (
                id INTEGER PRIMARY KEY,
                plan_date DATE NOT NULL,
                meal_time VARCHAR NOT NULL,
                recipe_id INTEGER,
                FOREIGN KEY(plan_date) REFERENCES meal_plans(plan_date) ON DELETE CASCADE,
                FOREIGN KEY(recipe_id) REFERENCES recipes(id)
            )
            """
        )
    )
    conn.execute(
        sa.text(
            """
            INSERT INTO meal_slots_new(id, plan_date, meal_time, recipe_id)
            SELECT ms.id, mp.plan_date, ms.meal_time, ms.recipe_id
            FROM meal_slots AS ms
            JOIN meal_plans AS mp ON mp.id = ms.meal_plan_id
            """
        )
    )

    conn.execute(sa.text("DROP TABLE meal_slots"))
    conn.execute(sa.text("ALTER TABLE meal_slots_new RENAME TO meal_slots"))
    conn.execute(sa.text("DROP TABLE meal_plans"))
    conn.execute(sa.text("ALTER TABLE meal_plans_new RENAME TO meal_plans"))


def init_db() -> None:
    """Create database tables and run migrations if needed."""

    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        _migrate_plan_date_pk(conn)
