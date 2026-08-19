"""RA-5 / FC-7 / D-4 — one stylesheet, no literals in the templates.

"Design values MUST NOT be duplicated as literals across templates" is only a
requirement if something fails when they are. These tests are that something:
they grep the templates for hex colours and pixel literals and fail on a hit.
"""

import os
import re

import pytest

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES_DIR = os.path.join(BACKEND_DIR, "templates", "public")
STYLESHEET = os.path.join(BACKEND_DIR, "static", "public.css")
FRONTEND_TOKENS = os.path.join(
    os.path.dirname(BACKEND_DIR), "frontend-v2", "src", "index.css"
)

_HEX = re.compile(r"#[0-9a-fA-F]{3,8}\b")
_PX = re.compile(r"\b\d+(?:\.\d+)?px\b")
_REM = re.compile(r"\b\d+(?:\.\d+)?rem\b")
_STYLE_ATTR = re.compile(r"style\s*=", re.IGNORECASE)
_VAR_USE = re.compile(r"var\(\s*(--[\w-]+)")
_VAR_DEF = re.compile(r"^\s*(--[\w-]+)\s*:", re.MULTILINE)


def template_files():
    found = []
    for root, _dirs, files in os.walk(TEMPLATES_DIR):
        for name in files:
            if name.endswith(".html"):
                found.append(os.path.join(root, name))
    return found


def read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def css():
    return read(STYLESHEET)


def css_rules():
    """The stylesheet with comments removed, for scans about what it *does*."""
    return re.sub(r"/\*.*?\*/", "", css(), flags=re.S)


# --- the stylesheet exists and is the only one ----------------------------


def test_public_stylesheet_exists():
    assert os.path.isfile(STYLESHEET)


def test_templates_reference_exactly_one_stylesheet():
    hrefs = []
    for path in template_files():
        hrefs += re.findall(r'<link[^>]+href="([^"]+)"', read(path))
    assert hrefs == ["/static/public.css"]


def test_there_are_template_files_to_scan():
    """Guards the greps below from passing vacuously."""
    assert len(template_files()) >= 5


# --- RA-5: no design literals in the templates ---------------------------


@pytest.mark.parametrize("path", template_files(), ids=os.path.basename)
def test_template_contains_no_hex_colour(path):
    assert not _HEX.findall(read(path))


@pytest.mark.parametrize("path", template_files(), ids=os.path.basename)
def test_template_contains_no_pixel_or_rem_literal(path):
    body = read(path)
    assert not _PX.findall(body)
    assert not _REM.findall(body)


@pytest.mark.parametrize("path", template_files(), ids=os.path.basename)
def test_template_has_no_inline_style_attribute(path):
    assert not _STYLE_ATTR.search(read(path))


@pytest.mark.parametrize("path", template_files(), ids=os.path.basename)
def test_template_has_no_style_element(path):
    assert "<style" not in read(path).lower()


@pytest.mark.parametrize("path", template_files(), ids=os.path.basename)
def test_template_has_no_script_element(path):
    assert "<script" not in read(path).lower()


# --- the stylesheet itself ------------------------------------------------


def test_stylesheet_defines_a_root_token_block():
    assert ":root" in css()


def test_every_token_used_is_defined_in_the_stylesheet():
    body = css()
    defined = set(_VAR_DEF.findall(body))
    used = set(_VAR_USE.findall(body))
    for path in template_files():
        used |= set(_VAR_USE.findall(read(path)))
    assert used <= defined, sorted(used - defined)


def test_stylesheet_makes_no_off_origin_request():
    """It is served unauthenticated: it must not phone anywhere."""
    body = css_rules()
    assert "@import" not in body
    for url in re.findall(r"url\(\s*['\"]?([^'\")]+)", body):
        assert not url.startswith(("http://", "https://", "//")), url


def test_stylesheet_contains_no_user_or_account_data():
    body = css_rules().lower()
    for needle in ("token", "user_id", "recipe_id", "score"):
        assert needle not in body, needle
    assert not re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", body)


def test_stylesheet_mirrors_the_frontend_token_values():
    """RA-5: one source of truth for the design values.

    Only the tokens the public page actually uses are compared -- the public
    page is not obliged to carry the whole SPA palette, but the values it shares
    must not drift.
    """
    frontend = read(FRONTEND_TOKENS)
    frontend_tokens = dict(
        re.findall(r"^\s*(--[\w-]+)\s*:\s*([^;]+);", frontend, flags=re.MULTILINE)
    )
    public_tokens = dict(
        re.findall(r"^\s*(--[\w-]+)\s*:\s*([^;]+);", css(), flags=re.MULTILINE)
    )
    shared = set(frontend_tokens) & set(public_tokens)
    assert shared, "the public stylesheet shares no token with the SPA"
    for name in sorted(shared):
        assert (
            public_tokens[name].strip() == frontend_tokens[name].strip()
        ), f"{name} has drifted from frontend-v2/src/index.css"


def test_stylesheet_uses_the_design_guide_palette():
    body = css()
    for value in ("#0C3A2D", "#BD210F", "#6D9773", "#FFB902"):
        assert value in body, value


def test_stylesheet_declares_a_responsive_layout():
    assert "@media" in css()


def test_stylesheet_respects_reduced_motion_or_declares_no_animation():
    body = css()
    assert "prefers-reduced-motion" in body or "animation" not in body


def test_every_class_used_in_a_template_is_styled():
    """A class in the markup with no rule is a design value that went missing."""
    body = css()
    used = set()
    for path in template_files():
        for attr in re.findall(r'class="([^"]+)"', read(path)):
            used |= set(attr.split())
    undefined = {name for name in used if f".{name}" not in body}
    assert not undefined, sorted(undefined)
