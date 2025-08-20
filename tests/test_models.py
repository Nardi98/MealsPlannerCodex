from meal_planner.models import Ingredient, Recipe, RecipeIngredient, Tag


def test_recipe_links_ingredients_and_tags():
    ing = Ingredient(name="Tomato")
    tag = Tag(name="vegan")
    recipe = Recipe(title="Salad", servings_default=2, prep_time_min=5)
    ri = RecipeIngredient(ingredient=ing, qty_value=100, qty_unit="g")
    recipe.ingredients.append(ri)
    recipe.tags.append(tag)
    tag.recipes.append(recipe)
    assert recipe.ingredients[0].ingredient.name == "Tomato"
    assert tag.recipes[0] is recipe
