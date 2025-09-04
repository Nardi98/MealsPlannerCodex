from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "006_add_leftover_column"
down_revision = "005_meal_side_dishes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "meals",
        sa.Column("leftover", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.alter_column("meals", "leftover", server_default=None)


def downgrade() -> None:
    op.drop_column("meals", "leftover")
