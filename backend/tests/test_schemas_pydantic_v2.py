"""Pins Pydantic v2 migration: no v1-style config, no deprecation warnings."""
import warnings

import pytest
from pydantic import PydanticDeprecatedSince20
from pydantic import BaseModel

import schemas


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
