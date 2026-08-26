"""cascade meal rows on recipe delete

Deleting a recipe used to SET NULL on ``meals.recipe_id``, leaving a ghost row
the read path skipped while its ``meal_number`` still occupied the day. Any
such rows already in the database are corruption from that bug, so they are
deleted before the constraint is swapped.

Revision ID: b7c1e4a92f10
Revises: 3fc2051c6e3c
Create Date: 2026-08-26

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'b7c1e4a92f10'
down_revision: Union[str, Sequence[str], None] = '3fc2051c6e3c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("DELETE FROM meals WHERE recipe_id IS NULL")
    op.drop_constraint('meals_recipe_id_fkey', 'meals', type_='foreignkey')
    op.create_foreign_key(
        'meals_recipe_id_fkey',
        'meals',
        'recipes',
        ['recipe_id'],
        ['id'],
        ondelete='CASCADE',
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('meals_recipe_id_fkey', 'meals', type_='foreignkey')
    op.create_foreign_key(
        'meals_recipe_id_fkey',
        'meals',
        'recipes',
        ['recipe_id'],
        ['id'],
        ondelete='SET NULL',
    )
