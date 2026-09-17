"""system recipe catalog

Schema for the server-side recipe catalog ("Discover"), spec §4, §5 and §9:

* ``catalog_entries`` -- one row per catalogued recipe, keyed on the recipe
  itself (DM-1/DM-2), with both CHECK constraints named explicitly so
  autogenerate can match them on every later revision (MIG-2).
* ``recipes.source_recipe_id`` gains an index: the adoption count groups copies
  by it on every catalog listing (DM-5, MIG-5).
* ``users.is_system`` and ``users.is_admin``, NOT NULL with a false server
  default so existing rows are valid without a backfill (MIG-3).
* ``uq_user_single_system``, a unique *partial* index that allows at most one
  system account (SYS-2, MIG-4).

Schema only (MIG-8 / INIT-12): the catalog's recipes and the system account are
created by ``main._bootstrap`` at startup, never by a migration.

Reviewed by hand after autogenerate (MIG-6): the booleans use ``sa.false()``
and the partial index's predicate is an explicit ``sa.text``.

Revision ID: 67f3715acf44
Revises: a1d4f7b2c903
Create Date: 2026-09-13 19:58:41.587149

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '67f3715acf44'
down_revision: Union[str, Sequence[str], None] = 'a1d4f7b2c903'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'catalog_entries',
        sa.Column('recipe_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(), server_default='published', nullable=False),
        sa.Column('published_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('retired_at', sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            "status IN ('published', 'retired')",
            name='ck_catalog_entry_status',
        ),
        sa.CheckConstraint(
            "(status = 'retired') = (retired_at IS NOT NULL)",
            name='ck_catalog_entry_retired_all_or_nothing',
        ),
        sa.ForeignKeyConstraint(['recipe_id'], ['recipes.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('recipe_id'),
    )
    op.create_index(
        'ix_recipes_source_recipe_id', 'recipes', ['source_recipe_id'], unique=False
    )
    op.add_column(
        'users',
        sa.Column('is_system', sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.add_column(
        'users',
        sa.Column('is_admin', sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.create_index(
        'uq_user_single_system',
        'users',
        ['is_system'],
        unique=True,
        postgresql_where=sa.text('is_system'),
    )


def downgrade() -> None:
    """Downgrade schema: reverse every step of ``upgrade`` (MIG-7)."""
    op.drop_index('uq_user_single_system', table_name='users')
    op.drop_column('users', 'is_admin')
    op.drop_column('users', 'is_system')
    op.drop_index('ix_recipes_source_recipe_id', table_name='recipes')
    op.drop_table('catalog_entries')
