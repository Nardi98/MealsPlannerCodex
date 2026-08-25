"""No request may issue DDL.

``import_data`` and ``export_data`` used to call ``Base.metadata.create_all`` on
every invocation. That was harmless while the schema was whatever the models
said; with Alembic owning the schema it is actively dangerous -- a request could
recreate a table a migration had just dropped, and the version table would go on
claiming the migration had succeeded. Schema changes belong to
``alembic upgrade head`` and to nothing else.
"""

import io
import json

import pytest

import crud
from database import Base


@pytest.fixture
def forbid_ddl(monkeypatch):
    def _explode(*args, **kwargs):
        raise AssertionError("a request issued DDL; only migrations may do that")

    monkeypatch.setattr(Base.metadata, "create_all", _explode)
    monkeypatch.setattr(Base.metadata, "drop_all", _explode)


def test_export_issues_no_ddl(forbid_ddl, db_session, user):
    crud.export_data(session=db_session, user_id=user.id)


def test_import_issues_no_ddl(forbid_ddl, db_session, user):
    payload = io.StringIO(json.dumps({"recipes": [], "ingredients": [], "tags": []}))

    crud.import_data(payload, session=db_session, user_id=user.id)
