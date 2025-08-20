"""Utility helpers for SI unit conversions.

This module provides minimal conversion logic without external
dependencies. It supports kilograms, grams, milligrams, liters and
milliliters and offers helpers for converting quantities to canonical
base units and selecting sensible display units.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

MassUnit = Literal["kg", "g", "mg"]
VolumeUnit = Literal["L", "mL"]
QtyUnit = Literal["kg", "g", "mg", "L", "mL"]


_ALLOWED_UNITS: dict[QtyUnit, float] = {
    "kg": 1000.0,
    "g": 1.0,
    "mg": 0.001,
    "L": 1000.0,
    "mL": 1.0,
}


@dataclass
class Quantity:
    value: float
    unit: QtyUnit

    def to_base_units(self, density_g_per_ml: float | None = None) -> tuple[float, QtyUnit]:
        """Return the quantity expressed in grams for mass or using density for volume."""
        validate_unit(self.unit)
        if self.unit in {"kg", "g", "mg"}:
            grams = self.value * _ALLOWED_UNITS[self.unit]
            return grams, "g"
        if density_g_per_ml is None:
            raise ValueError("density_g_per_ml is required for volume ↔ mass conversion")
        ml = self.value * _ALLOWED_UNITS[self.unit]
        grams = ml * density_g_per_ml
        return grams, "g"

    def to_best_unit(self) -> tuple[float, QtyUnit]:
        """Return quantity in kg/g or L/mL depending on magnitude."""
        validate_unit(self.unit)
        if self.unit in {"kg", "g", "mg"}:
            grams = self.value * _ALLOWED_UNITS[self.unit]
            if grams >= 1000:
                return grams / 1000, "kg"
            return grams, "g"
        ml = self.value * _ALLOWED_UNITS[self.unit]
        if ml >= 1000:
            return ml / 1000, "L"
        return ml, "mL"


def validate_unit(unit: str) -> QtyUnit:
    if unit not in _ALLOWED_UNITS:
        raise ValueError(f"Unit '{unit}' is not allowed. Use SI units only: {sorted(_ALLOWED_UNITS)}")
    return unit  # type: ignore[return-value]


__all__ = ["Quantity", "validate_unit", "QtyUnit", "MassUnit", "VolumeUnit"]
