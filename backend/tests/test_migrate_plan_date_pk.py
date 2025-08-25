from datetime import date

import sqlalchemy as sa

from database import _migrate_plan_date_pk


def test_migrate_plan_date_pk(tmp_path):
    db_file = tmp_path / "old.db"
    engine = sa.create_engine(f"sqlite:///{db_file}", future=True)

    metadata = sa.MetaData()
    meal_plans = sa.Table(
        "meal_plans",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("plan_date", sa.Date),
    )
    meal_slots = sa.Table(
        "meal_slots",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("meal_plan_id", sa.Integer),
        sa.Column("meal_time", sa.String),
        sa.Column("recipe_id", sa.Integer),
    )
    metadata.create_all(engine)

    with engine.begin() as conn:
        conn.execute(
            meal_plans.insert(), [{"id": 1, "plan_date": date(2024, 1, 1)}]
        )
        conn.execute(
            meal_slots.insert(),
            [{"id": 1, "meal_plan_id": 1, "meal_time": "dinner", "recipe_id": None}],
        )

        _migrate_plan_date_pk(conn)

        insp = sa.inspect(conn)
        slot_cols = {c["name"] for c in insp.get_columns("meal_slots")}
        assert "plan_date" in slot_cols
        assert "meal_plan_id" not in slot_cols

        slots = conn.execute(sa.text("SELECT plan_date FROM meal_slots"))
        assert slots.fetchone()[0] == "2024-01-01"

        plans = conn.execute(sa.text("SELECT plan_date FROM meal_plans"))
        assert plans.fetchall() == [("2024-01-01",)]

