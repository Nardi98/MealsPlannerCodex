"""The block renderer for public recipe pages (RA-6, FC-1, FC-3, D-3).

This release only ever renders one layout, so a block renderer looks like
over-engineering. It is not: FC-1 requires that enabling Part 2's public pages
must not introduce a second renderer, and the cheapest way to guarantee that is
to make the *only* renderer block-driven from the start. Part 2 adds a name to
:data:`BLOCK_TYPES` and a partial next to the others; it never touches the loop
in ``templates/public/recipe.html``.

Unknown block types are **dropped rather than raised** (FC-1): ``page_layout`` is
a JSON column that a future release writes, so an older deploy reading a newer
layout must degrade to the blocks it understands instead of 500-ing on the
product's only unauthenticated surface.
"""

from __future__ import annotations

import functools
import os
from dataclasses import dataclass
from typing import Any

from fastapi.templating import Jinja2Templates

from public_copy import course_label
from public_markup import render_markup, safe_url

TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")

#: FC-3: the order SP-1 mandates.
DEFAULT_BLOCKS = ("hero", "ingredients", "steps", "attribution", "author")

#: Every type this release knows how to render. No ``notes`` type is registered:
#: ``notes`` was struck from SP-1/PRV-2 because ``Recipe`` has no such column.
BLOCK_TYPES = frozenset(DEFAULT_BLOCKS)


@dataclass(frozen=True)
class Block:
    """A typed, self-contained piece of the page.

    ``data`` holds everything the partial needs, so a partial never reaches back
    into the page context. That is what makes the set of blocks reorderable and
    reusable by Part 2 without touching either the template or this module.
    """

    type: str
    data: dict[str, Any]


def _block_data(block_type: str, recipe) -> dict[str, Any]:
    if block_type == "hero":
        return {
            "title": recipe.title,
            "image_url": recipe.image_url,
            "author_display_name": recipe.author_display_name,
            "author_username": recipe.author_username,
            "servings": recipe.servings,
            "course": recipe.course,
            "tags": list(recipe.tags),
        }
    if block_type == "ingredients":
        return {"ingredients": list(recipe.ingredients), "servings": recipe.servings}
    if block_type == "steps":
        # Rendered here rather than in the template so the escape-first renderer
        # is applied exactly once, at a point that is unit-tested.
        return {"procedure": render_markup(recipe.procedure)}
    if block_type == "attribution":
        return {"attribution": recipe.attribution}
    if block_type == "author":
        return {
            "author_display_name": recipe.author_display_name,
            "author_username": recipe.author_username,
        }
    raise KeyError(block_type)  # pragma: no cover - guarded by BLOCK_TYPES


def _requested_types(layout) -> list[str]:
    """Normalise ``page_layout`` to a list of type names.

    ``layout`` arrives from a JSON column, so it may be anything at all. Only a
    list is honoured; every other shape falls back to the defaults (FC-3).
    """
    if layout is None or not isinstance(layout, list):
        return list(DEFAULT_BLOCKS)

    names: list[str] = []
    for entry in layout:
        if isinstance(entry, str):
            names.append(entry)
        elif isinstance(entry, dict) and isinstance(entry.get("type"), str):
            names.append(entry["type"])
    return names


def build_blocks(public_recipe, layout=None) -> list[Block]:
    """Build the ordered block list for ``public_recipe``.

    ``layout is None`` selects :data:`DEFAULT_BLOCKS` (FC-3). Types this release
    does not know are dropped silently (FC-1), and a block with nothing to say
    -- an attribution block on a recipe that is not a copy -- is dropped too, so
    no partial has to render an empty section.
    """
    blocks: list[Block] = []
    for name in _requested_types(layout):
        if name not in BLOCK_TYPES:
            continue
        if name == "attribution" and public_recipe.attribution is None:
            continue
        blocks.append(Block(type=name, data=_block_data(name, public_recipe)))
    return blocks


@functools.lru_cache(maxsize=1)
def public_templates() -> Jinja2Templates:
    """The public rendering environment.

    ``Jinja2Templates`` turns autoescaping on, which is the single property the
    whole public surface rests on (D-1); ``tests/test_blocks.py`` asserts it
    rather than trusting it. ``undefined`` is left at Jinja's default so a
    missing context key renders empty instead of raising on a visitor's page.
    """
    templates = Jinja2Templates(directory=TEMPLATES_DIR)
    templates.env.autoescape = True
    templates.env.trim_blocks = True
    templates.env.lstrip_blocks = True
    templates.env.filters["safe_url"] = safe_url
    templates.env.filters["quantity"] = format_quantity
    templates.env.globals["course_label"] = course_label
    return templates


def format_quantity(value) -> str:
    """Render a quantity without a pointless trailing ``.0``."""
    if value is None:
        return ""
    try:
        number = float(value)
    except (TypeError, ValueError):  # pragma: no cover - defensive
        return ""
    if number == int(number):
        return str(int(number))
    return "{:g}".format(round(number, 2))
