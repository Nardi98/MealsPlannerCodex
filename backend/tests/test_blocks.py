"""RA-6 / FC-1 / FC-3 — the block renderer, and PRV-3 on what it renders.

No route is involved: the templates are rendered through a directly
instantiated environment, exactly as Phase 2B will render them.
"""

import datetime
import re

import pytest

from blocks import (
    BLOCK_TYPES,
    DEFAULT_BLOCKS,
    Block,
    build_blocks,
    public_templates,
)
from public_copy import t
from public_schema import PublicAttribution, PublicIngredient, PublicRecipe


def make_recipe(**overrides) -> PublicRecipe:
    base = dict(
        title="Pasta al forno",
        image_url="https://cdn.example/img.jpg",
        servings=4,
        procedure="Boil the water.\n\nDrain and bake.",
        ingredients=[
            PublicIngredient(name="Farina", quantity=250.0, unit="g"),
            PublicIngredient(name="Sale", quantity=None, unit=None),
        ],
        tags=["comfort", "domenica"],
        course="main",
        author_display_name="Anna Rossi",
        author_username="anna",
        attribution=None,
    )
    base.update(overrides)
    return PublicRecipe(**base)


def render(recipe=None, **context):
    """Render ``public/recipe.html`` the way Phase 2B will."""
    recipe = recipe or make_recipe()
    template = public_templates().get_template("public/recipe.html")
    ctx = {
        "recipe": recipe,
        "blocks": build_blocks(recipe, None),
        "lang": "it",
        "t": lambda key, **fmt: t(context.get("lang", "it"), key, **fmt),
        "copy_url": None,
        "page_url": "https://app.example/s/TOKEN",
        "image_url": recipe.image_url,
    }
    ctx.update(context)
    return template.render(**ctx)


# --- the renderer ---------------------------------------------------------


def test_default_blocks_are_the_fc3_order():
    assert DEFAULT_BLOCKS == ("hero", "ingredients", "steps", "attribution", "author")


def test_block_types_registered_equals_the_default_list():
    """No ``notes`` block type is registered (decision on SP-1/PRV-2)."""
    assert BLOCK_TYPES == frozenset(DEFAULT_BLOCKS)
    assert "notes" not in BLOCK_TYPES


def test_layout_none_uses_the_defaults():
    types = [b.type for b in build_blocks(make_recipe(), None)]
    # attribution drops out when there is nothing to attribute.
    assert types == ["hero", "ingredients", "steps", "author"]


def test_attribution_block_appears_when_the_recipe_is_a_copy():
    recipe = make_recipe(
        attribution=PublicAttribution(
            author_username="chef",
            recipe_title="Ragu",
            copied_at=datetime.datetime(2026, 1, 2),
        )
    )
    assert "attribution" in [b.type for b in build_blocks(recipe, None)]


def test_explicit_layout_is_honoured_in_order():
    types = [b.type for b in build_blocks(make_recipe(), ["steps", "hero"])]
    assert types == ["steps", "hero"]


def test_unknown_block_types_are_dropped_not_raised():
    """FC-1: Part 2 may write a layout this release does not understand."""
    blocks = build_blocks(make_recipe(), ["hero", "gallery", "nutrition", "steps"])
    assert [b.type for b in blocks] == ["hero", "steps"]


def test_layout_entries_may_be_dicts_with_a_type_key():
    blocks = build_blocks(make_recipe(), [{"type": "hero"}, {"type": "nope"}])
    assert [b.type for b in blocks] == ["hero"]


def test_malformed_layout_degrades_to_the_defaults():
    for layout in ("hero", 7, {"hero": 1}):
        types = [b.type for b in build_blocks(make_recipe(), layout)]
        assert types[0] == "hero"


def test_empty_layout_renders_nothing():
    assert build_blocks(make_recipe(), []) == []


def test_block_is_immutable_and_carries_its_own_data():
    block = build_blocks(make_recipe(), ["hero"])[0]
    assert isinstance(block, Block)
    assert block.data["title"] == "Pasta al forno"
    with pytest.raises(Exception):
        block.type = "other"


def test_every_registered_type_has_a_partial():
    env = public_templates().env
    for name in BLOCK_TYPES:
        env.get_template(f"public/blocks/{name}.html")


# --- the environment ------------------------------------------------------


def test_autoescape_is_enabled():
    """The single property the whole rendering stack rests on (D-1)."""
    assert public_templates().env.autoescape is True


def test_autoescape_is_active_for_the_actual_templates():
    env = public_templates().env
    rendered = env.from_string("{{ x }}").render(x="<script>alert(1)</script>")
    assert "<script>" not in rendered


# --- rendering ------------------------------------------------------------


def test_page_renders_the_recipe():
    html = render()
    assert "Pasta al forno" in html
    assert "Farina" in html
    assert "Anna Rossi" in html
    assert "anna" in html


def test_title_is_escaped_in_every_position():
    html = render(make_recipe(title='<script>alert(1)</script>'))
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def assert_no_injected_attribute(html: str) -> None:
    """No tag in the document may carry an attacker-supplied attribute.

    Escaped payload text is harmless, so the assertion is scoped to the markup
    regions -- the only bytes that are not escaped.
    """
    for tag in re.findall(r"<[^>]*>", html):
        lowered = tag.lower()
        for needle in ("onerror", "onload", "onmouseover", "javascript:", "data:"):
            assert needle not in lowered, f"{needle!r} inside tag {tag!r}"


def test_ingredient_names_are_escaped():
    recipe = make_recipe(
        ingredients=[PublicIngredient(name='<img src=x onerror=alert(1)>')]
    )
    html = render(recipe)
    assert_no_injected_attribute(html)
    assert "&lt;img" in html


def test_tag_names_are_escaped():
    html = render(make_recipe(tags=['" onmouseover="alert(1)']))
    assert_no_injected_attribute(html)
    assert "&#34;" in html or "&quot;" in html


def test_author_name_is_escaped():
    html = render(make_recipe(author_display_name="</title><script>x</script>"))
    assert "<script>" not in html


def test_image_url_with_a_javascript_scheme_is_not_emitted():
    html = render(make_recipe(image_url="javascript:alert(1)"))
    assert "javascript:" not in html.lower()


def test_image_url_with_a_data_scheme_is_not_emitted():
    html = render(make_recipe(image_url="data:text/html,<script>alert(1)</script>"))
    assert "data:text/html" not in html.lower()


def test_procedure_is_rendered_through_the_restricted_markup_renderer():
    recipe = make_recipe(procedure="**bold**\n\n<script>alert(1)</script>")
    html = render(recipe)
    assert "<strong>bold</strong>" in html
    assert "<script>alert(1)</script>" not in html


def test_missing_ingredients_and_procedure_render_a_message_not_a_crash():
    html = render(make_recipe(ingredients=[], procedure=None))
    assert t("it", "no_ingredients") in html
    assert t("it", "no_steps") in html


def test_missing_image_renders_without_an_img_tag():
    html = render(make_recipe(image_url=None))
    assert "<img" not in html


def test_page_declares_its_language():
    assert 'lang="it"' in render()
    assert 'lang="en"' in render(lang="en", t=lambda k, **f: t("en", k, **f))


def test_page_is_noindex():
    html = render()
    assert 'name="robots"' in html
    assert "noindex" in html


def test_page_has_no_json_ld_and_no_canonical():
    html = render()
    assert "application/ld+json" not in html
    assert 'rel="canonical"' not in html
    assert "schema.org" not in html


def test_page_links_the_shared_stylesheet_and_no_other_origin():
    html = render()
    assert "/static/public.css" in html
    for url in re.findall(r'(?:href|src)="([^"]+)"', html):
        assert not url.startswith("http://"), url
        if url.startswith("https://"):
            assert url == "https://cdn.example/img.jpg", url


def test_copy_cta_renders_only_when_a_url_is_supplied():
    assert t("it", "copy_cta") not in render()
    html = render(copy_url="https://app.example/shared/TOKEN")
    assert t("it", "copy_cta") in html
    assert 'href="https://app.example/shared/TOKEN"' in html


def test_servings_form_works_without_javascript():
    html = render()
    assert "<form" in html
    assert 'method="get"' in html
    assert 'name="servings"' in html


def test_page_contains_no_script_element_of_its_own():
    """SP-11/PRV-6: the page must be complete with JavaScript off."""
    html = render()
    assert "<script" not in html.lower()


# --- PRV-3 ----------------------------------------------------------------

PRV3_FORBIDDEN = (
    "score",
    "bulk_prep",
    "date_last_consumed",
    "date_last_rejected",
    "plan_settings",
    "default_people",
    "user_id",
    "recipe_id",
    "meal_plan",
    "@test.local",
    "owner@",
)


def _all_text_including_comments(html: str) -> str:
    # HTML comments are explicitly in scope for PRV-3; they are part of ``html``
    # already, so the assertion is simply that nothing was hidden in one.
    return html.lower()


def test_rendered_page_contains_no_prv3_forbidden_token():
    html = _all_text_including_comments(render())
    for needle in PRV3_FORBIDDEN:
        assert needle not in html, needle


def test_rendered_page_contains_no_email_address():
    assert not re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", render())


def test_rendered_page_contains_no_other_share_token():
    html = render(copy_url="https://app.example/shared/TOKEN")
    assert "OTHERTOKEN" not in html
    # Exactly one token appears: the one the visitor already holds.
    assert html.count("TOKEN") <= 2


def test_html_comments_carry_no_data():
    comments = re.findall(r"<!--(.*?)-->", render(), flags=re.S)
    for comment in comments:
        assert "Pasta al forno" not in comment
        assert "anna" not in comment.lower()


def test_numeric_ids_are_not_reachable_from_the_public_model():
    """PRV-3: there is no id to render, because the schema has no id field."""
    assert "id" not in PublicRecipe.model_fields
    assert "id" not in PublicIngredient.model_fields
