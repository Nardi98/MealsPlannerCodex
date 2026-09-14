"""Guards the architectural invariants CLAUDE.md declares, in one place.

Each section below defends a rule that is easy to violate accidentally and
expensive to discover later. They live together because none is large enough to
justify its own module and all of them answer the same question: "is the
codebase still wired the way the docs say it is?"

- Import layout -- one canonical set of ORM models / db / crud (audit #8), and
  ``catalog.py`` imports no router and no ``main`` (CAT-11).
- Scoping -- production calls to user-scoped ``crud``/``planner`` functions pass
  ``user_id``.
- Pydantic v2 -- no v1-style ``class Config``, no deprecation warnings.
- Runtime DDL -- Alembic owns the schema; no request may issue DDL.
- Destructive seed -- ``reset_database`` is gated behind an explicit opt-in.
"""
import ast
import importlib
import io
import json
import sys
import warnings
from pathlib import Path

import pytest
import sqlalchemy as sa
from pydantic import BaseModel, PydanticDeprecatedSince20

import crud
import schemas
from database import Base

from scripts.seed_testing_data import ALLOW_DESTRUCTIVE_SEED_ENV, reset_database

BACKEND_ROOT = Path(__file__).resolve().parent.parent


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


def _imported_modules(path):
    """Every module name ``path`` imports, read from its AST (not by importing it)."""
    names = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_catalog_service_imports_no_router_and_no_main():
    """CAT-11 / TST-11: startup, seed scripts and routers all call ``catalog``.

    It must not reach back into ``main``, any router or the frontend, or it
    could no longer be imported from startup without a cycle.
    """
    imported = _imported_modules(BACKEND_ROOT / "catalog.py")
    assert imported, "the AST walk found no imports at all"

    forbidden = {
        name
        for name in imported
        if name.split(".")[0] in {"main", "public_pages", "ops_routes"}
        or name.split(".")[0].endswith("_routes")
        or "frontend" in name.replace("-", "_").split(".")[0]
    }
    assert forbidden == set()


def _user_scoped_functions(path):
    """``{name: index of user_id among positional params, or None if keyword-only}``."""
    scoped = {}
    for node in ast.parse(path.read_text(encoding="utf-8")).body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        positional = [arg.arg for arg in node.args.posonlyargs + node.args.args]
        if "user_id" in positional:
            scoped[node.name] = positional.index("user_id")
        elif any(arg.arg == "user_id" for arg in node.args.kwonlyargs):
            scoped[node.name] = None
    return scoped


def _unscoped_calls(path, targets):
    """Calls in ``path`` to a user-scoped function that do not pass ``user_id``.

    ``targets`` maps a defining module's stem to its scoped functions. A call
    matches as ``<module>.<fn>(...)`` (``crud.get_recipe``, ``planner.generate_plan``)
    or, inside the defining module itself, as a bare ``<fn>(...)``. Anything
    else with the same name -- ``auth_users.create_refresh_token`` -- is a
    different function and is not matched.
    """
    found = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
            module, name = func.value.id, func.attr
        elif isinstance(func, ast.Name):
            module, name = path.stem, func.id
        else:
            continue
        scoped = targets.get(module, {})
        if name not in scoped:
            continue
        position = scoped[name]
        by_keyword = any(keyword.arg == "user_id" for keyword in node.keywords)
        by_position = position is not None and len(node.args) > position
        if not (by_keyword or by_position):
            found.append(f"{path.relative_to(BACKEND_ROOT).as_posix()}:{node.lineno} {module}.{name}")
    return found


def _production_modules():
    """Backend-root modules plus ``mealplanner/`` -- never tests, scripts or migrations."""
    return sorted(BACKEND_ROOT.glob("*.py")) + sorted((BACKEND_ROOT / "mealplanner").glob("*.py"))


def test_production_calls_to_user_scoped_functions_pass_user_id():
    """Every production call to a ``crud``/``planner`` function taking ``user_id`` passes it.

    Omitting it silently widens the query to every account's rows (``scope``
    treats ``None`` as unscoped), which is a data leak rather than an error. A
    call that is unscoped on purpose says so by passing ``user_id=None``.
    """
    targets = {
        "crud": _user_scoped_functions(BACKEND_ROOT / "crud.py"),
        "planner": _user_scoped_functions(BACKEND_ROOT / "mealplanner" / "planner.py"),
    }
    assert targets["crud"] and targets["planner"], "found no user-scoped functions to check"

    unscoped = [
        call
        for path in _production_modules()
        for call in _unscoped_calls(path, targets)
    ]

    assert unscoped == []


def test_the_scoping_guard_resolves_positional_keyword_and_same_named_calls(tmp_path, monkeypatch):
    """The guard's own matching rules, on a fixture module."""
    monkeypatch.setattr(sys.modules[__name__], "BACKEND_ROOT", tmp_path)
    module = tmp_path / "sample.py"
    module.write_text(
        "crud.get_or_create_ingredient(session, None, name, system.id)\n"
        "crud.get_or_create_ingredient(session, None, name)\n"
        "crud.get_recipe(session, 1, user_id=2)\n"
        "auth_users.create_refresh_token(session, user)\n"
        "crud.create_refresh_token(session)\n",
        encoding="utf-8",
    )
    targets = {"crud": {"get_or_create_ingredient": 3, "get_recipe": 2, "create_refresh_token": None}}

    assert _unscoped_calls(module, targets) == [
        "sample.py:2 crud.get_or_create_ingredient",
        "sample.py:5 crud.create_refresh_token",
    ]


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
