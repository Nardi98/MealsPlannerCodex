"""user feedback

The three tables behind in-app user feedback:

* ``feedback_items`` -- one filed report. ``type`` / ``status`` / ``priority``
  are plain strings held to their value sets by **named** CHECKs (not PG enums),
  so autogenerate can match the reflected constraints on later revisions.
  ``user_id`` is provenance, not ownership: ``ON DELETE SET NULL`` so a report
  outlives the account that filed it. ``updated_at`` is the schema's first
  generic change stamp, the natural sort for a triage inbox.
* ``feedback_tags`` -- admin labels, unique by their normalized name.
* ``feedback_item_tags`` -- the link, ``ON DELETE CASCADE`` on both sides.

Schema only: no row is created by a migration. Reviewed by hand after
autogenerate; ``downgrade`` reverses every step.

Revision ID: 5b0b58b9044e
Revises: c71bc3b77870
Create Date: 2026-10-04 21:21:24.415918

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5b0b58b9044e'
down_revision: Union[str, Sequence[str], None] = 'c71bc3b77870'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('feedback_tags',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_feedback_tags_name'), 'feedback_tags', ['name'], unique=True)
    op.create_table('feedback_items',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('ref_code', sa.String(), nullable=False),
    sa.Column('title', sa.String(), nullable=False),
    sa.Column('body', sa.Text(), nullable=False),
    sa.Column('type', sa.String(), nullable=False),
    sa.Column('status', sa.String(), server_default='open', nullable=False),
    sa.Column('priority', sa.String(), server_default='normal', nullable=False),
    sa.Column('seen', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('page_path', sa.String(), nullable=True),
    sa.Column('user_agent', sa.String(), nullable=True),
    sa.Column('viewport_width', sa.Integer(), nullable=True),
    sa.Column('screenshot_key', sa.String(), nullable=True),
    sa.Column('admin_notes', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("priority IN ('low', 'normal', 'high')", name='ck_feedback_item_priority'),
    sa.CheckConstraint("status IN ('open', 'in_progress', 'closed_fixed', 'closed_ignored')", name='ck_feedback_item_status'),
    sa.CheckConstraint("type IN ('issue', 'request', 'improvement', 'not_working')", name='ck_feedback_item_type'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_feedback_items_ref_code'), 'feedback_items', ['ref_code'], unique=True)
    op.create_table('feedback_item_tags',
    sa.Column('item_id', sa.Integer(), nullable=False),
    sa.Column('tag_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['item_id'], ['feedback_items.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['tag_id'], ['feedback_tags.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('item_id', 'tag_id')
    )


def downgrade() -> None:
    """Downgrade schema: reverse every step of ``upgrade``."""
    op.drop_table('feedback_item_tags')
    op.drop_index(op.f('ix_feedback_items_ref_code'), table_name='feedback_items')
    op.drop_table('feedback_items')
    op.drop_index(op.f('ix_feedback_tags_name'), table_name='feedback_tags')
    op.drop_table('feedback_tags')
