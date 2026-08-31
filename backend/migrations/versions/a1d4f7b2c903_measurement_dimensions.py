"""narrow stored units to one per dimension and give ingredients their physics

Units used to be opaque strings: two of them either matched or they did not,
and nothing could convert between them. A quantity is now a physical amount
that happens to be written in one of several equivalent ways.

Three things follow, and this revision does all three:

* ``recipe_ingredients`` keeps only base metric units. Existing ``kg`` and ``l``
  rows are multiplied by a thousand into ``g`` and ``ml``; the wide vocabulary
  (``cup``, ``oz``, ``kg``) becomes *formatting*, applied by the frontend at
  render time and never stored.
* ``ingredients`` loses ``unit`` and gains ``grams_per_ml`` and
  ``grams_per_piece``, the only two numbers needed to cross a dimension, plus
  ``preferred_dimension``, a display preference. All three start NULL, and NULL
  is a meaningful answer -- "this dimension does not apply" -- never a gap the
  app fills in with a guess.
* ``users`` gains ``unit_system``, which is display-only: the database stays
  metric whatever it says.

Dropping ``ingredients.unit`` discards its values, and ``downgrade`` cannot
bring them back. That is deliberate and safe: the column carried no information
``recipe_ingredients.unit`` does not already hold, and every reader now takes
the recipe line's own unit as authoritative.

Steps 2 to 4 are hand-written because autogenerate does not compare enum values
and cannot infer the data conversion.

Revision ID: a1d4f7b2c903
Revises: 2ca32a5d0e51
Create Date: 2026-08-31 11:52:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1d4f7b2c903'
down_revision: Union[str, Sequence[str], None] = '2ca32a5d0e51'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Alembic stores this enum by *member name*, not by value, so the SQL below
# compares against 'KG' and 'L' rather than 'kg' and 'l'.
WIDE_UNITS = ('G', 'KG', 'L', 'ML', 'PIECE')
NARROW_UNITS = ('G', 'ML', 'PIECE')

dimension_enum = sa.Enum('MASS', 'VOLUME', 'PIECE', name='dimension_enum')


def _replace_unit_enum(members: Sequence[str]) -> None:
    """Swap ``unit_enum`` for one holding exactly ``members``.

    Postgres cannot remove a value from an enum, so the type is rebuilt and the
    single remaining column repointed at it. This runs *after*
    ``ingredients.unit`` is dropped, when ``recipe_ingredients.unit`` is the
    only user of the type.
    """
    values = ', '.join(f"'{m}'" for m in members)
    op.execute(f"CREATE TYPE unit_enum_new AS ENUM ({values})")
    op.execute(
        "ALTER TABLE recipe_ingredients ALTER COLUMN unit TYPE unit_enum_new "
        "USING unit::text::unit_enum_new"
    )
    op.execute("DROP TYPE unit_enum")
    op.execute("ALTER TYPE unit_enum_new RENAME TO unit_enum")


def upgrade() -> None:
    """Upgrade schema."""
    # 1. The new columns. Every one starts NULL or metric, so nothing about an
    #    existing account's behaviour changes on day one.
    dimension_enum.create(op.get_bind(), checkfirst=True)
    op.add_column('ingredients', sa.Column('grams_per_ml', sa.Float(), nullable=True))
    op.add_column('ingredients', sa.Column('grams_per_piece', sa.Float(), nullable=True))
    op.add_column(
        'ingredients',
        sa.Column('preferred_dimension', dimension_enum, nullable=True),
    )
    op.add_column(
        'users',
        sa.Column(
            'unit_system', sa.String(), server_default='metric', nullable=False
        ),
    )

    # 2. Rewrite the quantities that are about to lose their unit. This must
    #    happen while 'KG' and 'L' are still valid members of the type.
    op.execute(
        "UPDATE recipe_ingredients SET quantity = quantity * 1000, unit = 'G' "
        "WHERE unit = 'KG'"
    )
    op.execute(
        "UPDATE recipe_ingredients SET quantity = quantity * 1000, unit = 'ML' "
        "WHERE unit = 'L'"
    )

    # 3. The ingredient no longer owns a canonical unit.
    op.drop_column('ingredients', 'unit')

    # 4. Only base units are storable from here on.
    _replace_unit_enum(NARROW_UNITS)


def downgrade() -> None:
    """Downgrade schema.

    Reversible in shape but not in full: ``ingredients.unit`` comes back empty,
    because its values were discarded on the way up.
    """
    _replace_unit_enum(WIDE_UNITS)
    op.add_column(
        'ingredients',
        sa.Column('unit', sa.Enum(*WIDE_UNITS, name='unit_enum'), nullable=True),
    )

    # Send the thousand-fold rows back to kg and l. Anything below the boundary
    # was authored in the base unit and stays there.
    op.execute(
        "UPDATE recipe_ingredients SET quantity = quantity / 1000, unit = 'KG' "
        "WHERE unit = 'G' AND quantity >= 1000"
    )
    op.execute(
        "UPDATE recipe_ingredients SET quantity = quantity / 1000, unit = 'L' "
        "WHERE unit = 'ML' AND quantity >= 1000"
    )

    op.drop_column('users', 'unit_system')
    op.drop_column('ingredients', 'preferred_dimension')
    op.drop_column('ingredients', 'grams_per_piece')
    op.drop_column('ingredients', 'grams_per_ml')
    dimension_enum.drop(op.get_bind(), checkfirst=True)
