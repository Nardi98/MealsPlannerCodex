import mealplanner.db as db
from sqlalchemy import create_engine, inspect
import mealplanner.models  # ensure models are registered with Base


def test_init_db_creates_tables_and_is_idempotent():
    # Bind Base to a temporary in-memory SQLite engine
    test_engine = create_engine("sqlite:///:memory:", future=True)
    original_engine = db.engine
    try:
        db.engine = test_engine
        db.Base.metadata.bind = test_engine

        # Initial initialization should create tables
        db.init_db()
        inspector = inspect(test_engine)
        assert inspector.has_table("recipes")
        assert inspector.has_table("ingredients")
        assert inspector.has_table("tags")

        # Calling again should succeed and leave tables intact
        db.init_db()
        inspector = inspect(test_engine)
        assert inspector.has_table("recipes")
        assert inspector.has_table("ingredients")
        assert inspector.has_table("tags")
    finally:
        db.engine = original_engine
        db.Base.metadata.bind = original_engine
