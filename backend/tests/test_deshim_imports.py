"""Guards the de-shimmed import layout (audit #8).

After removing the ``sys.modules`` self-replacement shims there must be exactly
one canonical set of ORM models / db / crud, reachable via the top-level
modules, and the ``mealplanner`` package must NOT ship shim submodules that swap
themselves out at import time.
"""
import importlib

import pytest


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
    import crud
    import database
    import models

    assert hasattr(database, "Base")
    assert hasattr(crud, "create_recipe")
    assert hasattr(models, "Recipe")
