import schemas


class DummyRecipe:
    def __init__(self, user_id: int) -> None:
        self.id = 1
        self.title = "Example"
        self.servings_default = 4
        self.procedure = None
        self.bulk_prep = False
        self.course = "main"
        self.score = None
        self.date_last_consumed = None
        self.user_id = user_id
        self.ingredients = []
        self.tags = []


def test_recipe_out_includes_user_id() -> None:
    recipe = DummyRecipe(user_id=42)
    schema = schemas.RecipeOut.model_validate(recipe)
    assert schema.user_id == 42


def test_ingredient_summary_exposes_user_id() -> None:
    summary = schemas.IngredientSummary(
        id=1,
        name="Carrot",
        season_months=[],
        unit=None,
        recipe_count=0,
        user_id=99,
    )
    assert summary.user_id == 99


def test_ingredient_create_rejects_user_id() -> None:
    model = schemas.IngredientCreate(name="Carrot", season_months=[])
    assert "user_id" not in model.model_dump()
    assert not hasattr(model, "user_id")
