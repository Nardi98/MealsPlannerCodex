"""Create recipe_ingredients association table and migrate data."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "002_recipe_ingredients_table"
down_revision = "001_convert_season_months"
branch_labels = None
depends_on = None


unit_enum = sa.Enum("g", "kg", "l", "ml", "piece", name="unit_enum")


def upgrade() -> None:
    op.create_table(
        "recipe_ingredients",
        sa.Column(
            "recipe_id",
            sa.Integer(),
            sa.ForeignKey("recipes.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "ingredient_id",
            sa.Integer(),
            sa.ForeignKey("ingredients.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("quantity", sa.Float()),
        sa.Column("unit", unit_enum),
    )

    conn = op.get_bind()
    rows = conn.execute(
        sa.text(
            "SELECT id AS ingredient_id, recipe_id, quantity, unit FROM ingredients "
            "WHERE recipe_id IS NOT NULL"
        )
    ).fetchall()
    if rows:
        conn.execute(
            sa.text(
                "INSERT INTO recipe_ingredients (recipe_id, ingredient_id, quantity, unit) "
                "VALUES (:recipe_id, :ingredient_id, :quantity, :unit)"
            ),
            rows,
        )

    with op.batch_alter_table("ingredients") as batch_op:
        batch_op.drop_column("quantity")
        batch_op.drop_column("unit")
        batch_op.drop_column("recipe_id")


def downgrade() -> None:  # pragma: no cover - legacy support
    with op.batch_alter_table("ingredients") as batch_op:
        batch_op.add_column(sa.Column("recipe_id", sa.Integer(), sa.ForeignKey("recipes.id")))
        batch_op.add_column(sa.Column("quantity", sa.Float()))
        batch_op.add_column(sa.Column("unit", unit_enum))

    conn = op.get_bind()
    rows = conn.execute(
        sa.text(
            "SELECT recipe_id, ingredient_id, quantity, unit FROM recipe_ingredients"
        )
    ).fetchall()
    for row in rows:
        conn.execute(
            sa.text(
                "UPDATE ingredients SET recipe_id = :recipe_id, quantity = :quantity, unit = :unit "
                "WHERE id = :ingredient_id"
            ),
            row,
        )

    op.drop_table("recipe_ingredients")
