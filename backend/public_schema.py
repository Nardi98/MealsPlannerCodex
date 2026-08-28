"""The public serialiser (PRV-1, PRV-2, PRV-4, FC-6).

Everything the unauthenticated share page is allowed to know about a recipe
passes through :class:`PublicRecipe`. The models below deliberately do **not**
set ``from_attributes`` and there is no ``model_validate`` over the ORM
``Recipe``: reading attributes off the ORM object by name is a denylist in
disguise, and a denylist means every column added to ``Recipe`` in the future is
public by default. Instead :meth:`PublicRecipe.from_recipe` assigns each
permitted field by hand, so a new column is private until somebody writes a line
here — and ``tests/test_public_schema.py`` fails the moment that line changes the
field set.

Part 2 extends this module by adding fields (FC-6); it never restructures it.
"""

from __future__ import annotations

import datetime

from pydantic import BaseModel, ConfigDict

_STRICT = ConfigDict(extra="forbid", from_attributes=False)


class PublicIngredient(BaseModel):
    """An ingredient line: name, quantity, unit. Never the ingredient's id."""

    model_config = _STRICT

    name: str
    quantity: float | None = None
    unit: str | None = None


class PublicAttribution(BaseModel):
    """The AT-1 attribution snapshot, as the page renders it."""

    model_config = _STRICT

    author_username: str
    recipe_title: str
    copied_at: datetime.datetime | None = None


def _unit_str(unit) -> str | None:
    if unit is None:
        return None
    # ``UnitEnum`` members carry the display string in ``.value``.
    return getattr(unit, "value", unit)


class PublicRecipe(BaseModel):
    """Exactly the PRV-2 permitted fields, and nothing else."""

    model_config = _STRICT

    title: str
    image_url: str | None = None
    # The head-count these quantities are for: the recipe's authored basis from
    # ``from_recipe``, the requested target after ``scaled_to``, so the page can
    # echo the chosen head-count back into its servings form.
    servings: int
    procedure: str | None = None
    ingredients: list[PublicIngredient] = []
    tags: list[str] = []
    course: str
    author_display_name: str
    author_username: str
    attribution: PublicAttribution | None = None

    @classmethod
    def from_recipe(cls, recipe, author) -> "PublicRecipe":
        """Project an ORM ``Recipe`` plus its author onto the allowlist.

        ``author`` is passed in rather than walked off ``recipe`` so the caller
        controls which query loaded it (NF-2) and so no relationship traversal
        can accidentally reach a second user's rows.
        """
        attribution = None
        if recipe.source_author_username and recipe.source_recipe_title:
            attribution = PublicAttribution(
                author_username=recipe.source_author_username,
                recipe_title=recipe.source_recipe_title,
                copied_at=recipe.copied_at,
            )

        return cls(
            title=recipe.title,
            image_url=recipe.image_url,
            servings=recipe.servings,
            procedure=recipe.procedure,
            ingredients=[
                PublicIngredient(
                    name=link.ingredient.name,
                    quantity=link.quantity,
                    unit=_unit_str(link.unit or link.ingredient.unit),
                )
                for link in recipe.ingredients
            ],
            tags=[tag.name for tag in recipe.tags],
            course=recipe.course,
            author_display_name=author.display_name or author.username,
            author_username=author.username,
            attribution=attribution,
        )

    def scaled_to(self, servings: int) -> "PublicRecipe":
        """SP-2: a copy scaled to ``servings``, leaving ``self`` untouched.

        Quantities come out of :meth:`from_recipe` for ``self.servings`` people,
        so the factor is the ratio between the target and that basis -- not the
        target itself. Scaling happens on the server so the page works with
        JavaScript off. A non-positive or unchanged target is a no-op rather than
        an error: the input arrives from a query string on an unauthenticated
        page, so it must degrade rather than raise.
        """
        if servings <= 0 or servings == self.servings:
            return self.model_copy(deep=True)

        factor = servings / self.servings
        scaled = self.model_copy(deep=True)
        scaled.servings = servings
        for line in scaled.ingredients:
            if line.quantity is not None:
                line.quantity = round(line.quantity * factor, 2)
        return scaled
