"""Use plan_date as primary key for meal plans and update slots."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "003_meal_plan_date_pk"
down_revision = "002_recipe_ingredients_table"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    # remove duplicate meal plans keeping the earliest id for each date
    conn.execute(
        sa.text(
            "DELETE FROM meal_plans WHERE id NOT IN (SELECT MIN(id) FROM meal_plans GROUP BY plan_date)"
        )
    )

    # add plan_date column to meal_slots
    with op.batch_alter_table("meal_slots") as batch_op:
        batch_op.add_column(sa.Column("plan_date", sa.Date(), nullable=True))

    conn.execute(
        sa.text(
            "UPDATE meal_slots SET plan_date = (SELECT plan_date FROM meal_plans WHERE meal_plans.id = meal_slots.meal_plan_id)"
        )
    )

    with op.batch_alter_table("meal_slots") as batch_op:
        batch_op.alter_column("plan_date", nullable=False)
        batch_op.create_foreign_key(
            "meal_slots_plan_date_fkey",
            "meal_plans",
            ["plan_date"],
            ["plan_date"],
            ondelete="CASCADE",
        )
        batch_op.drop_constraint("meal_slots_meal_plan_id_fkey", type_="foreignkey")
        batch_op.drop_column("meal_plan_id")

    # drop id column and make plan_date primary key
    with op.batch_alter_table("meal_plans") as batch_op:
        batch_op.drop_column("id")
        batch_op.create_primary_key("meal_plans_pkey", ["plan_date"])


def downgrade() -> None:  # pragma: no cover - irreversible
    raise NotImplementedError("Downgrade not supported")
