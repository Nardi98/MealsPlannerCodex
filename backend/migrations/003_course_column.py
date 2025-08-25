"""Add course column to recipes."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "003_course_column"
down_revision = "002_recipe_ingredients_table"
branch_labels = None
depends_on = None


course_enum = sa.Enum(
    "FIRST_COURSE", "MAIN_DISH", "SIDE_DISH", name="course_enum"
)


def upgrade() -> None:
    course_enum.create(op.get_bind(), checkfirst=True)
    with op.batch_alter_table("recipes") as batch_op:
        batch_op.add_column(
            sa.Column(
                "course",
                course_enum,
                nullable=False,
                server_default="MAIN_DISH",
            )
        )

    conn = op.get_bind()
    conn.execute(sa.text("UPDATE recipes SET course = 'MAIN_DISH'"))


def downgrade() -> None:
    with op.batch_alter_table("recipes") as batch_op:
        batch_op.drop_column("course")
    course_enum.drop(op.get_bind(), checkfirst=True)

