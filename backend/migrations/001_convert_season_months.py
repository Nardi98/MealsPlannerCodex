"""Convert free-text season_months values to comma separated numbers."""

from __future__ import annotations

import re
from calendar import month_name, month_abbr

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "001_convert_season_months"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    month_map = {name.lower(): i for i, name in enumerate(month_name) if name}
    month_map.update({abbr.lower(): i for i, abbr in enumerate(month_abbr) if abbr})
    results = conn.execute(sa.text("SELECT id, season_months FROM ingredients")).fetchall()
    for rid, text in results:
        if not text:
            new = None
        else:
            tokens = re.split(r"[^A-Za-z0-9]+", text.lower())
            months = []
            for tok in tokens:
                if tok.isdigit():
                    m = int(tok)
                    if 1 <= m <= 12:
                        months.append(m)
                elif tok in month_map:
                    months.append(month_map[tok])
            new = ",".join(str(m) for m in sorted(set(months))) if months else None
        conn.execute(
            sa.text("UPDATE ingredients SET season_months = :val WHERE id = :id"),
            {"val": new, "id": rid},
        )


def downgrade() -> None:  # pragma: no cover - irreversibly cleans data
    pass
