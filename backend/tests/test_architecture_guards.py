"""Guards the architectural invariants CLAUDE.md declares, in one place.

Each section below defends a rule that is easy to violate accidentally and
expensive to discover later. They live together because none is large enough to
justify its own module and all of them answer the same question: "is the
codebase still wired the way the docs say it is?"

- Import layout -- one canonical set of ORM models / db / crud (audit #8).
- Pydantic v2 -- no v1-style ``class Config``, no deprecation warnings.
- Runtime DDL -- Alembic owns the schema; no request may issue DDL.
- Destructive seed -- ``reset_database`` is gated behind an explicit opt-in.
"""
import importlib
import io
import json
import warnings

import pytest
import sqlalchemy as sa
from pydantic import BaseModel, PydanticDeprecatedSince20

import crud
import schemas
from database import Base

from scripts.seed_testing_data import ALLOW_DESTRUCTIVE_SEED_ENV, reset_database


# --------------------------------------------------------------------------
# Import layout: after removing the ``sys.modules`` self-replacement shims there
# must be exactly one canonical set of ORM models / db / crud, reachable via the
# top-level modules, and the ``mealplanner`` package must NOT ship shim
# submodules that swap themselves out at import time.
# --------------------------------------------------------------------------
def test_single_canonical_model_set():
    """The models used by the planner are the top-level ``models`` objects."""
    import models
    from mealplanner import planner

    assert planner.Recipe is models.Recipe
    assert planner.Meal is models.Meal


def test_no_shim_submodules():
    """``mealplanner.models`` / ``.db`` / ``.crud`` shims are gone."""
    for name in ("mealplanner.models", "mealplanner.db", "mealplanner.crud"):
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module(name)


def test_canonical_modules_import_cleanly():
    """Top-level canonical modules resolve without the shims."""
    # The in-function imports ARE the assertion -- this test is about the
    # modules resolving on demand, so it must not lean on the module-level
    # ``import crud`` above having already bound the name.
    import crud  # noqa: F811
    import database
    import models

    assert hasattr(database, "Base")
    assert hasattr(crud, "create_recipe")
    assert hasattr(models, "Recipe")


# --------------------------------------------------------------------------
# Pydantic v2: pins the migration -- no v1-style config, no deprecation warnings.
# --------------------------------------------------------------------------
def _schema_models():
    return [
        obj
        for obj in vars(schemas).values()
        if isinstance(obj, type) and issubclass(obj, BaseModel) and obj is not BaseModel
    ]


def test_no_v1_class_config():
    """No schema should use the v1 `class Config` construct."""
    for model in _schema_models():
        assert "Config" not in vars(model), f"{model.__name__} still uses class Config"


def test_orm_models_use_from_attributes():
    """Models that read from ORM objects must set from_attributes=True."""
    for name in ("TagOut", "IngredientOut", "IngredientSummary", "RecipeSummary", "RecipeOut"):
        model = getattr(schemas, name)
        assert model.model_config.get("from_attributes") is True, name


def test_importing_and_validating_emits_no_pydantic_deprecation():
    class _Tag:
        id = 1
        name = "quick"

    with warnings.catch_warnings():
        warnings.simplefilter("error", PydanticDeprecatedSince20)
        out = schemas.TagOut.model_validate(_Tag())
    assert out.id == 1
    assert out.name == "quick"


# --------------------------------------------------------------------------
# Runtime DDL: ``import_data`` and ``export_data`` used to call
# ``Base.metadata.create_all`` on every invocation. That was harmless while the
# schema was whatever the models said; with Alembic owning the schema it is
# actively dangerous -- a request could recreate a table a migration had just
# dropped, and the version table would go on claiming the migration had
# succeeded. Schema changes belong to ``alembic upgrade head`` and nothing else.
# --------------------------------------------------------------------------
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


# --------------------------------------------------------------------------
# Destructive seed: ``reset_database`` calls ``Base.metadata.drop_all`` against
# whatever ``DATABASE_URL`` points at. On Railway that is production, so a single
# ``railway run python scripts/seed_testing_data.py`` would destroy every
# tester's data with no confirmation step. The opt-in env flag makes the
# destruction deliberate: local compose sets it, no deployment ever does.
#
# The final test really does drop and recreate every table. That is safe from
# any position: ``db_session`` issues no DDL and rolls back per test, so no
# test depends on rows or on a schema it did not build itself. Kept last only
# so a reader meets the cheap static checks first.
# --------------------------------------------------------------------------
def test_reset_database_refuses_to_run_without_the_flag(monkeypatch):
    monkeypatch.delenv(ALLOW_DESTRUCTIVE_SEED_ENV, raising=False)

    with pytest.raises(RuntimeError) as excinfo:
        reset_database()

    assert ALLOW_DESTRUCTIVE_SEED_ENV in str(excinfo.value)


@pytest.mark.parametrize("value", ["0", "true"])
def test_only_the_exact_opt_in_value_unlocks_the_reset(monkeypatch, value):
    """Anything other than ``1`` is refused.

    A truthy-ish string is exactly the sort of thing that gets left in a
    deployment's variables by accident, so the check is an equality test rather
    than a truthiness test.
    """
    monkeypatch.setenv(ALLOW_DESTRUCTIVE_SEED_ENV, value)

    with pytest.raises(RuntimeError):
        reset_database()


def test_the_flag_allows_the_reset(monkeypatch, engine):
    monkeypatch.setenv(ALLOW_DESTRUCTIVE_SEED_ENV, "1")

    reset_database()

    # Every mapped table is present again, so the reset ran to completion and
    # the rest of the suite still has a schema to work against.
    present = set(sa.inspect(engine).get_table_names())
    assert set(Base.metadata.tables).issubset(present)
