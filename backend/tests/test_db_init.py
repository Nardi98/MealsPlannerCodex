import database as db
from sqlalchemy import inspect
import models  # noqa: F401  ensure models are registered with Base


def test_init_db_creates_tables_and_is_idempotent(engine):
    """``init_db`` builds the schema and is safe to re-run."""
    db.Base.metadata.drop_all(bind=engine)

    for _ in range(2):  # the second call must be a no-op, not an error
        db.init_db()
        inspector = inspect(engine)
        for table in ("recipes", "ingredients", "tags"):
            assert inspector.has_table(table)
