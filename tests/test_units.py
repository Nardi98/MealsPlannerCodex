import pytest

from meal_planner.units import Quantity, validate_unit


def test_validate_unit_allows_si():
    assert validate_unit("g") == "g"
    with pytest.raises(ValueError):
        validate_unit("oz")


def test_to_base_units_mass():
    q = Quantity(2, "kg")
    value, unit = q.to_base_units()
    assert unit == "g"
    assert value == 2000


def test_volume_to_mass_requires_density():
    q = Quantity(1, "L")
    with pytest.raises(ValueError):
        q.to_base_units()
    value, unit = q.to_base_units(density_g_per_ml=1)
    assert unit == "g"
    assert value == 1000


def test_to_best_unit():
    assert Quantity(1500, "g").to_best_unit() == (1.5, "kg")
    assert Quantity(500, "mL").to_best_unit() == (500, "mL")
