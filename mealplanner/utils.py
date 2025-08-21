"""Utility helpers for the Meals Planner Codex application.

This module contains small, self‑contained helpers that are useful in a number
of places throughout the application.  They are intentionally lightweight and
do not pull in any third‑party dependencies so that they can be easily reused
both by the main code base and within tests.

Currently the module provides helpers for:

* Parsing ISO style date strings.
* Formatting :class:`datetime.date` objects.
* Converting between common weight units.

Each helper performs basic validation and raises a :class:`ValueError` with a
helpful message when something goes wrong.  The accompanying unit tests exercise
both the happy paths and the error handling code paths.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Union


def parse_date(value: Union[str, date, datetime], fmt: str = "%Y-%m-%d") -> date:
    """Parse *value* into a :class:`datetime.date`.

    Parameters
    ----------
    value:
        Either a string containing a date in ``fmt`` format, a
        :class:`datetime.date` or a :class:`datetime.datetime`.
    fmt:
        The expected format of *value* when it is a string.  Defaults to the
        common ``YYYY-MM-DD`` ISO format.

    Returns
    -------
    datetime.date
        The parsed date.

    Raises
    ------
    ValueError
        If *value* is a string that does not match *fmt*.
    TypeError
        If *value* is not a string or a date/datetime instance.
    """

    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        raise TypeError("value must be a str, date, or datetime instance")

    try:
        return datetime.strptime(value, fmt).date()
    except ValueError as exc:  # pragma: no cover - exercised in tests
        raise ValueError(f"Date '{value}' does not match format '{fmt}'") from exc


def format_date(value: Union[date, datetime], fmt: str = "%Y-%m-%d") -> str:
    """Return *value* formatted according to *fmt*.

    ``format_date(parse_date(s))`` will round‑trip for well formed ``s``.
    ``value`` may be either :class:`datetime.date` or :class:`datetime.datetime`.
    """

    if isinstance(value, datetime):
        value = value.date()
    if not isinstance(value, date):
        raise TypeError("value must be a date or datetime instance")
    return value.strftime(fmt)


_GRAM_CONVERSIONS = {
    "g": 1.0,
    "kg": 1000.0,
    "oz": 28.349523125,
    "lb": 453.59237,
}


def convert_units(value: float, from_unit: str, to_unit: str) -> float:
    """Convert *value* from ``from_unit`` to ``to_unit``.

    Only a handful of common weight units are supported: ``g``, ``kg``, ``oz``
    and ``lb``.  The conversion is performed by first converting to grams and
    then to the requested unit.  Negative values are rejected because weights
    cannot be negative in this context.
    """

    if value < 0:
        raise ValueError("value must be non-negative")

    from_unit = from_unit.lower()
    to_unit = to_unit.lower()

    try:
        grams = value * _GRAM_CONVERSIONS[from_unit]
        result = grams / _GRAM_CONVERSIONS[to_unit]
    except KeyError as exc:
        raise ValueError("unsupported unit conversion") from exc
    return result


__all__ = ["parse_date", "format_date", "convert_units"]

