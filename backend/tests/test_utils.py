import pytest
from datetime import date

from mealplanner.utils import parse_date, format_date


def test_parse_date_string():
    d = parse_date("2024-03-15")
    assert isinstance(d, date)
    assert d == date(2024, 3, 15)


def test_parse_date_invalid_format():
    with pytest.raises(ValueError):
        parse_date("15/03/2024")


def test_parse_date_type_error():
    with pytest.raises(TypeError):
        parse_date(1234)  # type: ignore[arg-type]


def test_format_date_round_trip():
    original = date(2023, 12, 25)
    formatted = format_date(original)
    assert formatted == "2023-12-25"
    # round-trip using parse_date
    assert parse_date(formatted) == original


def test_format_date_invalid_type():
    with pytest.raises(TypeError):
        format_date("2023-01-01")  # type: ignore[arg-type]
