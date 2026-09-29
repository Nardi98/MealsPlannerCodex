"""catalog import staging

The two tables behind the reviewed catalog import:

* ``catalog_import_batches`` -- one uploaded file. No status column: a batch's
  state is derivable from its items, and the batch is deleted once nothing is
  left to review.
* ``catalog_import_items`` -- one entry of that file, its untouched ``source``
  and the admin's ``draft``, both ``sa.JSON`` (generic, as everywhere else in
  ``models.py``; there is no JSONB precedent and ``tests/test_migrations.py``
  compares types exactly). ``state`` is constrained by a **named** CHECK so
  autogenerate can match the reflected one on every later revision (MIG-2).

Schema only: no batch is ever created by a migration.

Reviewed by hand after autogenerate (MIG-6). The two recipe foreign keys are
``ON DELETE SET NULL`` on purpose -- deleting a committed recipe must not erase
the item that records the commit -- while ``batch_id`` cascades, so pruning a
finished batch takes its items with it.

Revision ID: a60c6f33d41f
Revises: 67f3715acf44
Create Date: 2026-09-28 14:58:34.739599

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a60c6f33d41f'
down_revision: Union[str, Sequence[str], None] = '67f3715acf44'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('catalog_import_batches',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_by_user_id', sa.Integer(), nullable=False),
    sa.Column('filename', sa.String(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_catalog_import_batches_created_by_user_id'), 'catalog_import_batches', ['created_by_user_id'], unique=False)
    op.create_table('catalog_import_items',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('batch_id', sa.Integer(), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('source', sa.JSON(), nullable=False),
    sa.Column('draft', sa.JSON(), nullable=False),
    sa.Column('state', sa.String(), server_default='pending', nullable=False),
    sa.Column('error', sa.Text(), nullable=True),
    sa.Column('committed_recipe_id', sa.Integer(), nullable=True),
    sa.Column('duplicate_recipe_id', sa.Integer(), nullable=True),
    sa.CheckConstraint("state IN ('pending', 'invalid', 'skipped', 'committed')", name='ck_catalog_import_item_state'),
    sa.ForeignKeyConstraint(['batch_id'], ['catalog_import_batches.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['committed_recipe_id'], ['recipes.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['duplicate_recipe_id'], ['recipes.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('batch_id', 'position', name='uq_catalog_import_item_position')
    )
    op.create_index(op.f('ix_catalog_import_items_batch_id'), 'catalog_import_items', ['batch_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema: reverse every step of ``upgrade`` (MIG-7)."""
    op.drop_index(op.f('ix_catalog_import_items_batch_id'), table_name='catalog_import_items')
    op.drop_table('catalog_import_items')
    op.drop_index(op.f('ix_catalog_import_batches_created_by_user_id'), table_name='catalog_import_batches')
    op.drop_table('catalog_import_batches')
