"""Conversions accumulate; they are never overwritten and never invented.

Two rules run through every path that can learn a factor -- an import, a copied
share, a merge -- and they are the same rule stated twice:

* the database wins. A stored factor is the user's, and no automated source
  replaces it.
* absent is not wrong. A reply that omits a density is saying "this ingredient
  has no meaningful volume", which is recorded as NULL and left alone.

The system therefore gets more capable the more it is used, and can only ever
gain knowledge, never lose it.
"""

import pytest

import crud
from models import DimensionEnum, Ingredient, Recipe, RecipeIngredient, UnitEnum


def _ingredient(session, name, user, **factors):
    ing = Ingredient(name=name, user_id=user.id, **factors)
    session.add(ing)
    session.flush()
    return ing


def _line(session, recipe, ingredient, quantity, unit):
    line = RecipeIngredient(
        recipe_id=recipe.id,
        ingredient_id=ingredient.id,
        quantity=quantity,
        unit=unit,
    )
    session.add(line)
    session.flush()
    return line


def _recipe(session, user, title="Stew"):
    recipe = Recipe(title=title, user_id=user.id)
    session.add(recipe)
    session.flush()
    return recipe


class TestBackfill:
    def test_an_absent_factor_is_filled_in(self, db_session, user):
        _ingredient(db_session, "Onion", user)

        ing = crud.get_or_create_ingredient(
            db_session, None, "Onion", user_id=user.id, grams_per_piece=150
        )

        assert ing.grams_per_piece == 150

    def test_a_stored_factor_is_never_overwritten(self, db_session, user):
        _ingredient(db_session, "Onion", user, grams_per_piece=140)

        ing = crud.get_or_create_ingredient(
            db_session, None, "Onion", user_id=user.id, grams_per_piece=150
        )

        # The user's number stands. They may edit it; an import may not.
        assert ing.grams_per_piece == 140

    def test_an_omitted_factor_leaves_the_stored_one_alone(self, db_session, user):
        _ingredient(db_session, "Onion", user, grams_per_piece=140)

        ing = crud.get_or_create_ingredient(
            db_session, None, "Onion", user_id=user.id, grams_per_ml=None
        )

        assert ing.grams_per_piece == 140
        assert ing.grams_per_ml is None

    def test_a_new_ingredient_carries_whatever_it_was_taught(self, db_session, user):
        ing = crud.get_or_create_ingredient(
            db_session, None, "Flour", user_id=user.id, grams_per_ml=0.53
        )

        assert ing.grams_per_ml == 0.53
        # Flour has no useful piece weight, and nothing invents one.
        assert ing.grams_per_piece is None


class TestMerge:
    def test_a_line_is_converted_into_the_targets_dimension(self, db_session, user):
        source = _ingredient(db_session, "Tomatoes", user)
        target = _ingredient(
            db_session, "Tomato", user, grams_per_piece=120,
            preferred_dimension=DimensionEnum.MASS,
        )
        recipe = _recipe(db_session, user)
        _line(db_session, recipe, source, 2, UnitEnum.PIECE)

        crud.merge_ingredients(db_session, source.id, target.id, user_id=user.id)

        line = db_session.get(RecipeIngredient, (recipe.id, target.id))
        assert (line.quantity, line.unit) == (240, UnitEnum.G)

    def test_an_unconvertible_line_keeps_its_own_dimension(self, db_session, user):
        # The merged ingredient simply spans two dimensions, which the shopping
        # list already renders as two rows.
        source = _ingredient(db_session, "Tomatoes", user)
        target = _ingredient(db_session, "Tomato", user)
        recipe = _recipe(db_session, user)
        _line(db_session, recipe, source, 2, UnitEnum.PIECE)

        crud.merge_ingredients(db_session, source.id, target.id, user_id=user.id)

        line = db_session.get(RecipeIngredient, (recipe.id, target.id))
        assert (line.quantity, line.unit) == (2, UnitEnum.PIECE)

    def test_conversions_union_onto_the_target(self, db_session, user):
        source = _ingredient(db_session, "Tomatoes", user, grams_per_ml=1.05)
        target = _ingredient(db_session, "Tomato", user, grams_per_piece=120)

        merged = crud.merge_ingredients(
            db_session, source.id, target.id, user_id=user.id
        )

        assert merged.grams_per_piece == 120
        assert merged.grams_per_ml == 1.05

    def test_the_target_wins_a_collision(self, db_session, user):
        source = _ingredient(db_session, "Tomatoes", user, grams_per_piece=90)
        target = _ingredient(db_session, "Tomato", user, grams_per_piece=120)

        merged = crud.merge_ingredients(
            db_session, source.id, target.id, user_id=user.id
        )

        assert merged.grams_per_piece == 120

    def test_the_preferred_dimension_follows_the_target(self, db_session, user):
        source = _ingredient(
            db_session, "Tomatoes", user, grams_per_piece=90,
            preferred_dimension=DimensionEnum.PIECE,
        )
        target = _ingredient(
            db_session, "Tomato", user, grams_per_piece=120,
            preferred_dimension=DimensionEnum.MASS,
        )

        merged = crud.merge_ingredients(
            db_session, source.id, target.id, user_id=user.id
        )

        assert merged.preferred_dimension is DimensionEnum.MASS

    def test_colliding_lines_are_summed_in_the_targets_dimension(
        self, db_session, user
    ):
        source = _ingredient(db_session, "Tomatoes", user)
        target = _ingredient(db_session, "Tomato", user, grams_per_piece=120)
        recipe = _recipe(db_session, user)
        _line(db_session, recipe, source, 2, UnitEnum.PIECE)
        _line(db_session, recipe, target, 100, UnitEnum.G)

        crud.merge_ingredients(db_session, source.id, target.id, user_id=user.id)

        line = db_session.get(RecipeIngredient, (recipe.id, target.id))
        assert (line.quantity, line.unit) == (340, UnitEnum.G)

    def test_an_unconvertible_collision_refuses_the_merge(self, db_session, user):
        # The composite key permits one row per recipe and ingredient, so two
        # dimensions cannot both survive here -- and folding them would drop
        # the 2 pieces the user wrote down. Refusing says so; merging lies.
        source = _ingredient(db_session, "Tomatoes", user)
        target = _ingredient(db_session, "Tomato", user)
        recipe = _recipe(db_session, user)
        _line(db_session, recipe, source, 2, UnitEnum.PIECE)
        _line(db_session, recipe, target, 100, UnitEnum.G)

        with pytest.raises(ValueError) as excinfo:
            crud.merge_ingredients(
                db_session, source.id, target.id, user_id=user.id
            )

        # The refusal names the recipe and the field that would unblock it.
        assert "Stew" in str(excinfo.value)
        assert "One piece weighs" in str(excinfo.value)
        # Nothing was written: both lines, and both ingredients, still stand.
        assert db_session.get(RecipeIngredient, (recipe.id, source.id)).quantity == 2
        assert db_session.get(RecipeIngredient, (recipe.id, target.id)).quantity == 100
        assert db_session.get(Ingredient, source.id) is not None


class TestDataPortability:
    """A payload written before this change is still a valid payload."""

    def _payload(self, ingredient):
        import io
        import json
        return io.StringIO(json.dumps(
            {
                "recipes": [
                    {
                        "id": 1,
                        "title": "Stew",
                        "course": "main",
                        "ingredients": [ingredient],
                        "tags": [],
                    }
                ],
                "tags": [],
            }
        ))

    def test_a_pre_change_payload_normalises_its_kg_quantities(
        self, db_session, user
    ):
        crud.import_data(
            self._payload(
                {"id": 1, "name": "Rice", "quantity": 2, "unit": "kg"}
            ),
            db_session,
            mode="merge",
            user_id=user.id,
        )

        line = db_session.query(RecipeIngredient).one()
        assert (line.quantity, line.unit) == (2000, UnitEnum.G)

    def test_a_pre_change_payload_reads_conversions_as_null(
        self, db_session, user
    ):
        # Absent conversions are absent, and the data behaves as it does today.
        crud.import_data(
            self._payload({"id": 1, "name": "Rice", "quantity": 2, "unit": "g"}),
            db_session,
            mode="merge",
            user_id=user.id,
        )

        rice = db_session.query(Ingredient).filter_by(name="Rice").one()
        assert (rice.grams_per_ml, rice.grams_per_piece) == (None, None)

    def test_an_import_teaches_the_pantry_its_conversions(self, db_session, user):
        crud.import_data(
            self._payload(
                {
                    "id": 1,
                    "name": "Flour",
                    "quantity": 200,
                    "unit": "ml",
                    "grams_per_ml": 0.53,
                }
            ),
            db_session,
            mode="merge",
            user_id=user.id,
        )

        flour = db_session.query(Ingredient).filter_by(name="Flour").one()
        assert flour.grams_per_ml == 0.53

    def test_an_export_carries_the_conversions_it_knows(self, db_session, user):
        import json

        flour = _ingredient(db_session, "Flour", user, grams_per_ml=0.53)
        recipe = _recipe(db_session, user)
        _line(db_session, recipe, flour, 200, UnitEnum.ML)
        db_session.commit()

        exported = json.loads(crud.export_data(db_session, user.id))

        line = exported["recipes"][0]["ingredients"][0]
        assert line["grams_per_ml"] == 0.53
        assert line["grams_per_piece"] is None


class TestCopyingAShare:
    """Copying someone's recipe follows the same rule as an import."""

    def test_it_backfills_a_conversion_the_copier_lacks(
        self, db_session, user, other_user
    ):
        import recipe_copy

        flour = _ingredient(db_session, "Flour", user, grams_per_ml=0.53)
        source = _recipe(db_session, user, title="Bread")
        _line(db_session, source, flour, 200, UnitEnum.ML)
        _ingredient(db_session, "Flour", other_user)
        db_session.flush()

        recipe_copy.copy_recipe(db_session, source, other_user)

        theirs = (
            db_session.query(Ingredient)
            .filter_by(name="Flour", user_id=other_user.id)
            .one()
        )
        assert theirs.grams_per_ml == 0.53

    def test_it_never_overwrites_what_the_copier_already_knew(
        self, db_session, user, other_user
    ):
        flour = _ingredient(db_session, "Flour", user, grams_per_ml=0.53)
        source = _recipe(db_session, user, title="Bread")
        _line(db_session, source, flour, 200, UnitEnum.ML)
        _ingredient(db_session, "Flour", other_user, grams_per_ml=0.6)
        db_session.flush()

        import recipe_copy
        recipe_copy.copy_recipe(db_session, source, other_user)

        theirs = (
            db_session.query(Ingredient)
            .filter_by(name="Flour", user_id=other_user.id)
            .one()
        )
        assert theirs.grams_per_ml == 0.6


class TestTheRecipePayload:
    """A recipe line carries the ingredient's physics with it.

    Unification is a read-time job, so whatever renders a recipe or builds a
    shopping list needs the factors in the same payload as the amounts. Making
    the client fetch the pantry separately would just be the same join, done
    later and less reliably.
    """

    def test_a_recipe_line_reports_the_ingredients_conversions(
        self, auth_client, db_session, user
    ):
        onion = _ingredient(db_session, "Onion", user, grams_per_piece=150)
        onion.preferred_dimension = DimensionEnum.MASS
        recipe = _recipe(db_session, user, title="Soffritto")
        _line(db_session, recipe, onion, 2, UnitEnum.PIECE)
        db_session.commit()

        line = auth_client.get(f"/recipes/{recipe.id}").json()["ingredients"][0]

        assert line["quantity"] == 2
        assert line["unit"] == "piece"
        assert line["grams_per_piece"] == 150
        assert line["grams_per_ml"] is None
        assert line["preferred_dimension"] == "mass"
