from sqlalchemy import select

from mealplanner.models import Recipe, Tag
from mealplanner.seed import _create_recipe


def test_new_tag_creation_and_linking(db_session):
    _create_recipe(
        db_session,
        title="Tag Test Recipe",
        servings=1,
        procedure="Boil water.",
        ingredients=[],
        tags=["novel"],
    )
    db_session.commit()

    tag = db_session.execute(select(Tag).where(Tag.name == "novel")).scalar_one()
    recipe = db_session.execute(select(Recipe).where(Recipe.title == "Tag Test Recipe")).scalar_one()

    assert tag.name == "novel"
    assert tag in recipe.tags
    assert recipe in tag.recipes
