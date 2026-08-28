"""add recipe servings basis

Recipe ingredient quantities used to be stored per person. They are now stored
as authored, for ``recipes.servings`` people, and readers divide by that basis.
Every existing row was written per person, so the server default of 1 is the
correct backfill and leaves their shopping lists and share pages unchanged.

Revision ID: 2ca32a5d0e51
Revises: b7c1e4a92f10
Create Date: 2026-08-28 11:45:17.636148

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2ca32a5d0e51'
down_revision: Union[str, Sequence[str], None] = 'b7c1e4a92f10'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('recipes', sa.Column('servings', sa.Integer(), server_default='1', nullable=False))
    op.create_check_constraint('ck_recipe_servings_positive', 'recipes', 'servings >= 1')


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('ck_recipe_servings_positive', 'recipes', type_='check')
    op.drop_column('recipes', 'servings')
