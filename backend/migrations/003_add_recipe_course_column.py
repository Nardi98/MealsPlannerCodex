"""Add course column to recipes table."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "003_add_recipe_course_column"
down_revision = "002_recipe_ingredients_table"
branch_labels = None
depends_on = None

course_enum = sa.Enum("FIRST_COURSE", "MAIN_DISH", "SIDE_DISH", name="course_enum")


def upgrade() -> None:
    course_enum.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "recipes",
        sa.Column("course", course_enum, nullable=False, server_default="MAIN_DISH"),
    )
    op.alter_column("recipes", "course", server_default=None)


def downgrade() -> None:  # pragma: no cover - simple rollback
    op.drop_column("recipes", "course")
    course_enum.drop(op.get_bind(), checkfirst=True)
