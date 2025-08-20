"""Grocery list aggregation stub.

The full implementation will convert recipe ingredients into aggregated
shopping lists. This module provides a minimal interface to be expanded.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass
class GroceryItem:
    ingredient_id: int
    amount_value: float
    amount_unit: str


def aggregate(items: list[GroceryItem]) -> Dict[int, GroceryItem]:
    """Aggregate grocery items by ingredient id.

    In this placeholder implementation, items with the same ingredient are
    simply summed assuming identical units.
    """
    agg: Dict[int, GroceryItem] = {}
    for item in items:
        if item.ingredient_id in agg:
            existing = agg[item.ingredient_id]
            existing.amount_value += item.amount_value
        else:
            agg[item.ingredient_id] = GroceryItem(**vars(item))
    return agg
