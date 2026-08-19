"""A restricted markup renderer for user-supplied text (D-2, SP-9/10/11).

**This module is the security boundary of the product's only unauthenticated
surface. Read this docstring before changing a line of it.**

The design is *escape-first*, and the order is the entire point:

1. the input is escaped in full, so after this step the string provably
   contains no ``<`` and no ``>``;
2. only then are tags constructed, from the SP-10 allowlist
   (``strong em a ul ol li h2 h3 br p``) and from nothing else.

Consequently an unsafe substring never exists at any moment -- not transiently,
not inside an intermediate buffer. This is strictly stronger than the usual
parse-then-allowlist sanitiser, whose correctness depends on its parser agreeing
with every browser's parser about every malformed document. That is why there is
no ``bleach`` / ``lxml`` / ``html5lib`` dependency here and why one must never be
added: SP-11 forbids accepting or storing user HTML at all, so there is no HTML
in the database to sanitise in the first place.

The only place user data is emitted into a *markup* position is a link's
``href``, and a URL reaches that position only if it matches ``^https?://`` on
the already-escaped string. That single allowlist is what kills ``javascript:``,
``data:``, ``vbscript:``, and every whitespace- or control-character-obfuscated
spelling of them: the obfuscating characters are removed before the check, and
anything that then fails to look like an absolute http(s) URL is dropped
entirely, leaving the link's label as plain escaped text. Links carry
``rel="nofollow ugc"`` per SP-9.
"""

from __future__ import annotations

import re

from markupsafe import Markup, escape

#: SP-10, verbatim. Nothing outside this set is ever constructed.
ALLOWED_TAGS = frozenset(
    {"strong", "em", "a", "ul", "ol", "li", "h2", "h3", "br", "p"}
)

# Anchors are parked behind sentinels while emphasis is applied, so an asterisk
# or underscore inside a URL can never inject a tag into an ``href``. The
# sentinels are private-use code points and are stripped from the input below,
# so user text cannot forge one and steal an anchor's slot.
_SENTINEL_OPEN = chr(0xE000)
_SENTINEL_CLOSE = chr(0xE001)

# Control characters carry no meaning in a recipe and are the classic way of
# smuggling "java<TAB>script:" past a scheme check, so they go first -- together
# with the two sentinel code points.
_CONTROL_RE = re.compile(
    "[\x00-\x08\x0b-\x1f\x7f-\x9f" + _SENTINEL_OPEN + _SENTINEL_CLOSE + "]"
)

_H3_RE = re.compile(r"^###\s+(.+)$")
_H2_RE = re.compile(r"^##\s+(.+)$")
_UL_RE = re.compile(r"^[-*]\s+(.+)$")
_OL_RE = re.compile(r"^\d+[.)]\s+(.+)$")

# The URL group is deliberately permissive (``[^)]*``): a malformed or hostile
# URL must be *captured and rejected*, not left unmatched as literal text where
# an ``onmouseover=`` fragment would survive into the page as visible content.
_LINK_RE = re.compile(r"\[([^\[\]]*)\]\(([^)]*)\)")

# Applied to the escaped URL. Requires an absolute http(s) URL with a non-empty
# authority and no whitespace anywhere.
_SAFE_URL_RE = re.compile(r"^https?://[^\s/?#]+[^\s]*$", re.IGNORECASE)

_STRONG_RE = re.compile(r"\*\*(\S(?:.*?\S)?)\*\*")
_EM_STAR_RE = re.compile(r"(?<!\*)\*(\S(?:[^*]*?\S)?)\*(?!\*)")
_EM_UNDER_RE = re.compile(r"(?<!\w)_(\S(?:[^_]*?\S)?)_(?!\w)")


def _sentinel(index: int) -> str:
    return "{}{}{}".format(_SENTINEL_OPEN, index, _SENTINEL_CLOSE)


def _emphasis(text: str) -> str:
    """Bold and italic. Operates on already-escaped text; inserts tags only."""
    text = _STRONG_RE.sub(r"<strong>\1</strong>", text)
    text = _EM_STAR_RE.sub(r"<em>\1</em>", text)
    return _EM_UNDER_RE.sub(r"<em>\1</em>", text)


def _inline(text: str) -> str:
    """Links first (parked behind sentinels), then emphasis."""
    anchors: list[str] = []

    def _link(match: re.Match) -> str:
        label, url = match.group(1), match.group(2)
        if not _SAFE_URL_RE.match(url):
            # Not an http(s) URL: drop the link, keep the human-readable label.
            return label
        anchors.append(
            '<a href="{}" rel="nofollow ugc">{}</a>'.format(
                url, _emphasis(label)
            )
        )
        return _sentinel(len(anchors) - 1)

    text = _LINK_RE.sub(_link, text)
    text = _emphasis(text)
    for index, anchor in enumerate(anchors):
        text = text.replace(_sentinel(index), anchor)
    return text


def render_markup(text: str | None) -> Markup:
    """Render ``text`` to the SP-10 allowlist and return safe ``Markup``.

    Returning ``Markup`` tells Jinja not to escape the result a second time,
    which is safe precisely because every byte of user input inside it was
    escaped before any tag was built.
    """
    if text is None:
        return Markup("")

    normalised = str(text).replace("\r\n", "\n").replace("\r", "\n")
    normalised = _CONTROL_RE.sub("", normalised)
    if not normalised.strip():
        return Markup("")

    # THE load-bearing line. Everything after this point works on a string that
    # cannot contain markup.
    escaped = str(escape(normalised))

    out: list[str] = []
    paragraph: list[str] = []
    items: list[str] = []
    list_tag: str | None = None

    def flush_paragraph() -> None:
        if paragraph:
            out.append("<p>{}</p>".format("<br>".join(paragraph)))
            paragraph.clear()

    def flush_list() -> None:
        nonlocal list_tag
        if items:
            out.append(
                "<{tag}>{body}</{tag}>".format(
                    tag=list_tag,
                    body="".join("<li>{}</li>".format(i) for i in items),
                )
            )
            items.clear()
        list_tag = None

    for raw_line in escaped.split("\n"):
        line = raw_line.strip()
        if not line:
            flush_paragraph()
            flush_list()
            continue

        heading = _H3_RE.match(line) or _H2_RE.match(line)
        if heading:
            flush_paragraph()
            flush_list()
            level = "h3" if line.startswith("###") else "h2"
            out.append(
                "<{lvl}>{body}</{lvl}>".format(
                    lvl=level, body=_inline(heading.group(1).strip())
                )
            )
            continue

        bullet = _UL_RE.match(line)
        numbered = None if bullet else _OL_RE.match(line)
        if bullet or numbered:
            wanted = "ul" if bullet else "ol"
            flush_paragraph()
            if list_tag != wanted:
                flush_list()
                list_tag = wanted
            items.append(_inline((bullet or numbered).group(1).strip()))
            continue

        flush_list()
        paragraph.append(_inline(line))

    flush_paragraph()
    flush_list()
    return Markup("".join(out))


def safe_url(url: str | None) -> str | None:
    """Return ``url`` if it may be emitted into ``href``/``src``, else ``None``.

    Two shapes are permitted: an absolute ``http``/``https`` URL, and a
    same-origin absolute path (``/media/x.jpg``). Everything else -- including
    protocol-relative ``//host/x``, which inherits the page's scheme and is
    therefore an off-origin fetch in disguise -- is rejected.

    Templates reach this through the ``safe_url`` filter. It is *not* a
    substitute for autoescaping: it runs before it, so a permitted URL is still
    escaped on the way into the attribute.
    """
    if not url:
        return None
    candidate = _CONTROL_RE.sub("", str(url)).strip()
    if not candidate or any(ch.isspace() for ch in candidate):
        return None
    if candidate.startswith("//"):
        return None
    if candidate.startswith("/"):
        return candidate
    return candidate if _SAFE_URL_RE.match(candidate) else None
