from meal_planner.grocery import GroceryItem, aggregate


def test_aggregate_sums_items():
    items = [
        GroceryItem(ingredient_id=1, amount_value=100, amount_unit="g"),
        GroceryItem(ingredient_id=1, amount_value=50, amount_unit="g"),
        GroceryItem(ingredient_id=2, amount_value=1, amount_unit="L"),
    ]
    agg = aggregate(items)
    assert agg[1].amount_value == 150
    assert agg[2].amount_value == 1
