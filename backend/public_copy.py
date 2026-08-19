"""Bilingual copy for the public share page (D-9, Q-3).

A dict and forty lines of parsing rather than an i18n framework: there are two
languages, one page, and no plural rules or date formats to negotiate. Adding
gettext or babel here would buy nothing and would put a compiled artefact
(``.mo``) on the critical path of the one page that must never fail to render.

``pick_language`` reads ``Accept-Language``. The caller is expected to set
``Vary: Accept-Language`` on the response so no cache or link unfurler serves a
visitor the wrong language.
"""

from __future__ import annotations

import re

DEFAULT_LANGUAGE = "it"
SUPPORTED_LANGUAGES = ("it", "en")

CATALOG: dict[str, dict[str, str]] = {
    "it": {
        "shared_recipe": "Ricetta condivisa",
        "ingredients": "Ingredienti",
        "steps": "Preparazione",
        "servings": "Porzioni",
        "servings_for": "Per {count} persone",
        "update_servings": "Aggiorna",
        "by_author": "di {author}",
        "adapted_from": "Adattata da {title} di @{author}",
        "copy_cta": "Salva questa ricetta nel mio ricettario",
        "about_author": "Ricetta di",
        "no_ingredients": "Nessun ingrediente indicato.",
        "no_steps": "Nessuna preparazione indicata.",
        "privacy_note": (
            "Questa pagina è raggiungibile solo da chi possiede il link e non "
            "è indicizzata dai motori di ricerca."
        ),
        "tags": "Etichette",
        "course": "Portata",
        "course_main": "Secondo",
        "course_first-course": "Primo",
        "course_side": "Contorno",
        "recipe_image_alt": "Foto della ricetta {title}",
    },
    "en": {
        "shared_recipe": "Shared recipe",
        "ingredients": "Ingredients",
        "steps": "Method",
        "servings": "Servings",
        "servings_for": "Serves {count}",
        "update_servings": "Update",
        "by_author": "by {author}",
        "adapted_from": "Adapted from {title} by @{author}",
        "copy_cta": "Save this recipe to my recipe book",
        "about_author": "Recipe by",
        "no_ingredients": "No ingredients listed.",
        "no_steps": "No method given.",
        "privacy_note": (
            "This page is reachable only by people holding the link and is not "
            "indexed by search engines."
        ),
        "tags": "Tags",
        "course": "Course",
        "course_main": "Main",
        "course_first-course": "First course",
        "course_side": "Side",
        "recipe_image_alt": "Photo of the recipe {title}",
    },
}

# Bound so a hostile header cannot make the parser do meaningful work.
_MAX_HEADER = 512
_TAG_RE = re.compile(r"^([a-zA-Z]{1,8})(?:-[a-zA-Z0-9]{1,8})*$")


def pick_language(accept_language: str | None) -> str:
    """Return the best supported language for ``Accept-Language``.

    A naive q-value parse: split on commas, read ``;q=``, keep the
    highest-weighted entry whose primary subtag is supported. Anything
    unparseable degrades to :data:`DEFAULT_LANGUAGE` rather than raising --
    this runs on an unauthenticated page where a malformed header must not be
    able to produce a 500.
    """
    if not accept_language:
        return DEFAULT_LANGUAGE

    best_lang = DEFAULT_LANGUAGE
    best_q = 0.0
    for part in accept_language[:_MAX_HEADER].split(","):
        piece, _, params = part.strip().partition(";")
        piece = piece.strip()
        if not _TAG_RE.match(piece):
            continue
        primary = piece.split("-")[0].lower()
        if primary not in SUPPORTED_LANGUAGES:
            continue

        quality = 1.0
        _, _, raw_q = params.partition("q=")
        if raw_q:
            try:
                quality = float(raw_q.strip())
            except ValueError:
                quality = 1.0
            quality = min(max(quality, 0.0), 1.0)

        if quality > best_q:
            best_q, best_lang = quality, primary

    return best_lang if best_q > 0 else DEFAULT_LANGUAGE


def t(lang: str, key: str, **fmt: object) -> str:
    """Look ``key`` up in ``lang``, falling back to the default language.

    An unknown *key* raises ``KeyError`` on purpose: a typo in a template is a
    bug that must break a test, not render a blank line to a visitor.
    """
    entries = CATALOG.get(lang, CATALOG[DEFAULT_LANGUAGE])
    template = entries.get(key)
    if template is None:
        template = CATALOG[DEFAULT_LANGUAGE][key]
    return template.format(**fmt) if fmt else template


def course_label(lang: str, course: str | None) -> str:
    """Human label for a course, falling back to the raw value.

    A course this release has no translation for must render as itself rather
    than raise: the page is unauthenticated and must never 500.
    """
    if not course:
        return ""
    entries = CATALOG.get(lang, CATALOG[DEFAULT_LANGUAGE])
    return entries.get("course_{}".format(course), course)
