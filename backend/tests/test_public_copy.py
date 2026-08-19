"""D-9 / Q-3 — the bilingual copy catalog for the public page."""

import pytest

from public_copy import CATALOG, DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES, pick_language, t


def test_default_language_is_italian():
    assert DEFAULT_LANGUAGE == "it"


def test_supported_languages_are_italian_and_english():
    assert SUPPORTED_LANGUAGES == ("it", "en")


def test_both_catalogs_carry_exactly_the_same_keys():
    """A missing translation must fail here, not silently on the page."""
    assert set(CATALOG["it"]) == set(CATALOG["en"])


def test_no_catalog_entry_is_blank():
    for lang, entries in CATALOG.items():
        for key, value in entries.items():
            assert value.strip(), f"{lang}/{key} is blank"


@pytest.mark.parametrize(
    "header,expected",
    [
        (None, "it"),
        ("", "it"),
        ("it", "it"),
        ("it-IT", "it"),
        ("en", "en"),
        ("en-GB,en;q=0.9", "en"),
        ("en-US,en;q=0.9,it;q=0.8", "en"),
        ("it;q=0.8,en;q=0.9", "en"),
        ("en;q=0.3,it;q=0.7", "it"),
        ("fr-FR,fr;q=0.9", "it"),
        ("de,en;q=0.5", "en"),
        ("*", "it"),
        ("en;q=0", "it"),
        ("EN-us", "en"),
        ("   en  ", "en"),
        ("en;q=notanumber", "en"),
        ("en;q=1.5", "en"),
        (",,,", "it"),
        ("x" * 5000, "it"),
    ],
)
def test_pick_language(header, expected):
    assert pick_language(header) == expected


def test_t_returns_the_string_for_the_language():
    assert t("it", "ingredients") != t("en", "ingredients")


def test_t_falls_back_to_the_default_language_for_unknown_languages():
    assert t("fr", "ingredients") == t("it", "ingredients")


def test_t_formats_named_placeholders():
    assert "Anna" in t("en", "by_author", author="Anna")
    assert "Anna" in t("it", "by_author", author="Anna")


def test_t_raises_on_an_unknown_key():
    """A typo in a template must break a test, not render an empty page."""
    with pytest.raises(KeyError):
        t("it", "no_such_key_at_all")


def test_t_does_not_escape_or_mangle_the_argument():
    """Escaping is the template's job (autoescape), not the catalog's."""
    assert "<b>" in t("en", "by_author", author="<b>")


def test_required_keys_exist():
    for key in (
        "ingredients",
        "steps",
        "servings",
        "update_servings",
        "shared_recipe",
        "by_author",
        "adapted_from",
        "copy_cta",
        "about_author",
        "no_ingredients",
        "no_steps",
        "privacy_note",
    ):
        assert key in CATALOG["it"]
