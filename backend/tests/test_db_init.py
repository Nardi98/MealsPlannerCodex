import pytest

import mealplanner.db as db


def test_init_db_is_deprecated():
    with pytest.raises(RuntimeError) as excinfo:
        db.init_db()

    assert "alembic upgrade head" in str(excinfo.value)
