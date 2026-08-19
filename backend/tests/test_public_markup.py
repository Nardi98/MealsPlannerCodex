"""SP-9/SP-10/SP-11 — the restricted markup renderer.

The property under test is *escape-first*: the renderer escapes the whole input
before it constructs a single tag, so an unsafe substring never exists at any
moment, not even transiently. Everything below is therefore an assertion that
some attacker-controlled string comes out inert.
"""

import re

import pytest
from markupsafe import Markup

from public_markup import ALLOWED_TAGS, render_markup

# Words that are harmless as escaped *text* but catastrophic inside a tag.
DANGEROUS_IN_MARKUP = (
    "javascript:",
    "vbscript:",
    "data:",
    "onerror",
    "onload",
    "onclick",
    "onmouseover",
    "srcdoc",
)

_TAG_RE = re.compile(r"<[^>]*>")
_OK_SIMPLE = re.compile(r"</?(strong|em|ul|ol|li|h2|h3|br|p)>")
_OK_ANCHOR = re.compile(r'<a href="[^"<>]*" rel="nofollow ugc">')


def assert_inert(html: str) -> None:
    """Assert every ``<`` in ``html`` belongs to an allowlisted tag we built.

    Text content does not need checking: it is escaped, so it cannot be markup.
    What must be checked is the *markup regions*, because those are the only
    bytes the renderer emits unescaped.
    """
    tags = _TAG_RE.findall(html)
    assert html.count("<") == len(tags), f"stray '<' in {html!r}"
    for tag in tags:
        assert (
            _OK_SIMPLE.fullmatch(tag)
            or tag == "</a>"
            or _OK_ANCHOR.fullmatch(tag)
        ), f"tag {tag!r} is not an allowlisted construction (in {html!r})"
        lowered = tag.lower()
        for needle in DANGEROUS_IN_MARKUP:
            assert needle not in lowered, f"{needle!r} inside tag {tag!r}"
    assert "<!--" not in html


# --- basic contract -------------------------------------------------------


def test_returns_markup_so_jinja_does_not_double_escape():
    assert isinstance(render_markup("hello"), Markup)


def test_none_and_empty_render_to_empty_markup():
    assert str(render_markup(None)) == ""
    assert str(render_markup("")) == ""
    assert str(render_markup("   \n  ")) == ""


def test_allowed_tags_is_exactly_the_sp10_allowlist():
    assert ALLOWED_TAGS == frozenset(
        {"strong", "em", "a", "ul", "ol", "li", "h2", "h3", "br", "p"}
    )


# --- escaping -------------------------------------------------------------


def test_script_tag_is_escaped_not_stripped_and_not_executed():
    out = str(render_markup("<script>alert(1)</script>"))
    assert_inert(out)
    assert "&lt;script&gt;" in out


def test_ampersand_and_quotes_are_escaped():
    out = str(render_markup('Salt & pepper "to taste"'))
    assert_inert(out)
    assert "&amp;" in out
    assert "<" not in out.replace("<p>", "").replace("</p>", "")


def test_img_onerror_payload_is_inert():
    assert_inert(str(render_markup('<img src=x onerror="alert(1)">')))


def test_svg_onload_payload_is_inert():
    assert_inert(str(render_markup("<svg/onload=alert(1)>")))


def test_html_comment_injection_is_inert():
    out = str(render_markup("<!-- <script>alert(1)</script> -->"))
    assert_inert(out)
    assert "<!--" not in out


def test_style_tag_payload_is_inert():
    assert_inert(str(render_markup("<style>body{background:url(x)}</style>")))


# --- links: scheme allowlist ---------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "javascript:alert(1)",
        "JaVaScRiPt:alert(1)",
        "JAVASCRIPT:alert(1)",
        "  javascript:alert(1)",
        "java\tscript:alert(1)",
        "java\nscript:alert(1)",
        "java\rscript:alert(1)",
        "java\x00script:alert(1)",
        "jav\x09ascript:alert(1)",
        "vbscript:msgbox(1)",
        "data:text/html;base64,PHNjcmlwdD5hbGVydCgxKTwvc2NyaXB0Pg==",
        "data:text/html,<script>alert(1)</script>",
        "file:///etc/passwd",
        "//evil.example/x",
        "\\\\evil.example\\x",
        "mailto:someone@example.com",
        "tel:+390000000",
        "ftp://evil.example/x",
        "about:blank",
        "blob:https://evil.example/x",
    ],
)
def test_non_http_link_targets_never_become_hrefs(url):
    out = str(render_markup(f"[click me]({url})"))
    assert_inert(out)
    assert "href" not in out.lower()
    # The label survives as plain text rather than vanishing.
    assert "click me" in out


@pytest.mark.parametrize("scheme", ["http", "https", "HTTP", "HttPs"])
def test_http_and_https_links_are_rendered(scheme):
    out = str(render_markup(f"[site]({scheme}://example.com/a)"))
    assert f'href="{scheme}://example.com/a"' in out
    assert "site</a>" in out


def test_links_carry_rel_nofollow_ugc():
    out = str(render_markup("[site](https://example.com)"))
    assert 'rel="nofollow ugc"' in out


def test_links_open_without_leaking_the_opener():
    out = str(render_markup("[site](https://example.com)"))
    assert 'target="_blank"' not in out or "noopener" in out


# --- links: attribute breaking -------------------------------------------


def test_quote_in_url_cannot_break_out_of_the_href_attribute():
    out = str(render_markup('[x](https://e.com/" onmouseover="alert(1))'))
    assert_inert(out)
    assert "onmouseover=" not in out
    assert '"' not in out.split("href=")[-1].split(">")[0].strip('"')


def test_quote_in_link_text_cannot_inject_an_attribute():
    out = str(render_markup('[a" onerror="alert(1)](https://e.com)'))
    assert_inert(out)
    assert "&#34;" in out or "&quot;" in out


def test_angle_bracket_in_url_is_escaped():
    out = str(render_markup("[x](https://e.com/<script>)"))
    assert_inert(out)


def test_ampersand_in_url_is_escaped_as_an_entity():
    out = str(render_markup("[x](https://e.com/?a=1&b=2)"))
    assert "https://e.com/?a=1&amp;b=2" in out
    assert_inert(out)


# --- emphasis -------------------------------------------------------------


def test_bold_and_italic():
    out = str(render_markup("**bold** and *italic* and _also_"))
    assert "<strong>bold</strong>" in out
    assert "<em>italic</em>" in out
    assert "<em>also</em>" in out


def test_unbalanced_emphasis_is_left_as_literal_text():
    out = str(render_markup("**bold and *italic"))
    assert_inert(out)
    assert "<strong>" not in out
    assert "<em>" not in out


def test_nested_and_overlapping_emphasis_stays_inert():
    for payload in (
        "*a **b* c**",
        "***triple***",
        "**a *b* c**",
        "*_x_*",
        "****",
        "*" * 40,
    ):
        assert_inert(str(render_markup(payload)))


def test_emphasis_markers_do_not_leak_into_an_href():
    out = str(render_markup("[x](https://e.com/*a*b)"))
    href = out.split('href="')[1].split('"')[0]
    assert "<" not in href and ">" not in href


# --- block structure ------------------------------------------------------


def test_paragraphs_are_split_on_blank_lines():
    out = str(render_markup("one\n\ntwo"))
    assert out.count("<p>") == 2


def test_single_newline_becomes_a_line_break():
    out = str(render_markup("one\ntwo"))
    assert "<br>" in out or "<br/>" in out
    assert out.count("<p>") == 1


def test_headings():
    out = str(render_markup("## Big\n\n### Small"))
    assert "<h2>Big</h2>" in out
    assert "<h3>Small</h3>" in out


def test_heading_level_one_is_not_produced():
    out = str(render_markup("# Title"))
    assert "<h1>" not in out


def test_unordered_list():
    out = str(render_markup("- a\n- b"))
    assert "<ul>" in out and out.count("<li>") == 2
    assert "</ul>" in out


def test_ordered_list():
    out = str(render_markup("1. a\n2. b"))
    assert "<ol>" in out and out.count("<li>") == 2


def test_list_items_are_escaped():
    assert_inert(str(render_markup("- <script>alert(1)</script>")))


def test_heading_content_is_escaped():
    assert_inert(str(render_markup("## <img src=x onerror=alert(1)>")))


def test_every_generated_tag_is_balanced_enough_to_close_the_document():
    out = str(render_markup("## h\n\n- a\n- b\n\npara **x**\n\n[l](https://e.com)"))
    assert out.count("<ul>") == out.count("</ul>")
    assert out.count("<li>") == out.count("</li>")
    assert out.count("<p>") == out.count("</p>")
    assert out.count("<a ") == out.count("</a>")


# --- pathological input ---------------------------------------------------


@pytest.mark.parametrize(
    "payload",
    [
        "]]>",
        "<![CDATA[<script>alert(1)</script>]]>",
        "<!DOCTYPE html>",
        "<textarea>",
        "</p><script>alert(1)</script><p>",
        "[x](https://e.com)</a><script>alert(1)</script>",
        "[[[[x](https://e.com)",
        "[x](",
        "](https://e.com)",
        "\x00\x01\x02",
        "&lt;script&gt;alert(1)&lt;/script&gt;",
        "&#106;avascript:alert(1)",
        "[x](&#106;avascript:alert(1))",
        "[x](%6aavascript:alert(1))",
    ],
)
def test_pathological_payloads_render_inert(payload):
    assert_inert(str(render_markup(payload)))


def test_double_rendering_does_not_unescape():
    once = str(render_markup("<script>alert(1)</script>"))
    twice = str(render_markup(once))
    assert_inert(twice)
    assert "&amp;lt;" in twice


# --- safe_url (image and CTA attributes) ---------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "https://cdn.example/a.jpg",
        "http://cdn.example/a.jpg",
        "HTTPS://CDN.EXAMPLE/a.jpg",
        "/media/a.jpg",
        "/media/a b.jpg".replace(" ", "%20"),
    ],
)
def test_safe_url_allows_http_and_same_origin_paths(url):
    from public_markup import safe_url

    assert safe_url(url) == url


@pytest.mark.parametrize(
    "url",
    [
        None,
        "",
        "   ",
        "javascript:alert(1)",
        "JaVaScRiPt:alert(1)",
        "java\tscript:alert(1)",
        "data:text/html,<script>alert(1)</script>",
        "vbscript:x",
        "//evil.example/a.jpg",
        "\\\\evil.example\\a.jpg",
        "file:///etc/passwd",
        "mailto:a@b.example",
        "media/a.jpg",
        "https://cdn.example/a b.jpg",
        "about:blank",
    ],
)
def test_safe_url_rejects_everything_else(url):
    from public_markup import safe_url

    assert safe_url(url) is None


def test_render_markup_is_pure():
    text = "**a**"
    render_markup(text)
    assert text == "**a**"
