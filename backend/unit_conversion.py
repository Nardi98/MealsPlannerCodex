"""Crossing a dimension, server-side.

The frontend's ``utils/units.js`` owns the full picture: the fixed table that
turns ``cup`` into ``ml`` and the formatting that turns ``1200 g`` into
``1.2 kg``. Neither belongs here -- the database stores base units only, and
rendering is the client's job.

What the server does need is the second tier: ml -> g wants a density, piece ->
g wants a piece weight, and both live on the ingredient. Merging two
ingredients and copying a shared recipe both have to cross a dimension, and
both must refuse rather than guess when the factor is not there.
"""

from models import DimensionEnum, Ingredient, UnitEnum

_DIMENSION_OF_UNIT = {
    UnitEnum.G: DimensionEnum.MASS,
    UnitEnum.ML: DimensionEnum.VOLUME,
    UnitEnum.PIECE: DimensionEnum.PIECE,
}

_BASE_UNIT_OF_DIMENSION = {
    dimension: unit for unit, dimension in _DIMENSION_OF_UNIT.items()
}


# What kg and l were worth before they stopped being storable. A JSON payload
# exported before that change still says "kg", and it still means the same
# amount, so it is multiplied rather than rejected. This is the whole of Tier 1
# on the server: the paste path normalises the wide vocabulary client-side, and
# nothing else may enter through the API.
_LEGACY_UNITS = {
    "kg": (1000, UnitEnum.G),
    "l": (1000, UnitEnum.ML),
}


def normalise_to_base_unit(
    quantity: float | None, unit: str | None
) -> tuple[float | None, UnitEnum | None]:
    """Restate an incoming amount in the base unit of its dimension."""
    if not unit:
        return quantity, None
    if unit in _LEGACY_UNITS:
        factor, base = _LEGACY_UNITS[unit]
        return (quantity * factor if quantity is not None else None), base
    return quantity, UnitEnum(unit)


def dimension_of(unit: UnitEnum | None) -> DimensionEnum | None:
    """What ``unit`` measures, or ``None`` when the line states no unit."""
    return _DIMENSION_OF_UNIT.get(unit)


def base_unit_of(dimension: DimensionEnum) -> UnitEnum:
    """The single unit ``dimension`` is stored in."""
    return _BASE_UNIT_OF_DIMENSION[dimension]


def _factor(value: float | None) -> float | None:
    """A factor is only usable when it is a real, positive number.

    Zero is not a factor: crossing with it yields 0 or a division by zero, and
    both are lies of exactly the kind this module exists to avoid.
    """
    if value is None:
        return None
    return value if value > 0 else None


def convert(
    amount: float | None,
    from_dimension: DimensionEnum | None,
    to_dimension: DimensionEnum | None,
    ingredient: Ingredient | None,
) -> float | None:
    """Restate ``amount`` in ``to_dimension``, or return ``None``.

    ``None`` means the conversion is not available, and it is the honest
    answer: no factor is ever invented, water's density included. Volume to
    count is two hops through mass and therefore needs both factors.
    """
    if amount is None or from_dimension is None or to_dimension is None:
        return None
    if from_dimension == to_dimension:
        return amount
    if ingredient is None:
        return None

    density = _factor(ingredient.grams_per_ml)
    per_piece = _factor(ingredient.grams_per_piece)

    # Everything routes through mass, the dimension both factors are stated in.
    if from_dimension is DimensionEnum.MASS:
        grams = amount
    elif from_dimension is DimensionEnum.VOLUME:
        grams = amount * density if density else None
    else:
        grams = amount * per_piece if per_piece else None
    if grams is None:
        return None

    if to_dimension is DimensionEnum.MASS:
        return grams
    if to_dimension is DimensionEnum.VOLUME:
        return grams / density if density else None
    return grams / per_piece if per_piece else None


def reachable_dimensions(ingredient: Ingredient) -> list[DimensionEnum]:
    """Which dimensions this ingredient can be expressed in.

    An ingredient reaching a single dimension is a normal ingredient, not a
    broken one.
    """
    density = _factor(ingredient.grams_per_ml)
    per_piece = _factor(ingredient.grams_per_piece)
    if not density and not per_piece:
        return []

    reached = [DimensionEnum.MASS]
    if density:
        reached.append(DimensionEnum.VOLUME)
    if per_piece:
        reached.append(DimensionEnum.PIECE)
    return reached
