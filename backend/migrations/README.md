# Schema change history

This project has **no active migration system**. During development the schema is
created directly from the SQLAlchemy models by `Base.metadata.create_all` on startup
(`backend/main.py`), so a fresh database needs no migration step.

Real migrations will be introduced with `alembic init` when the project approaches
production and needs to evolve a populated database in place. Until then, changing the
schema means changing the model — nothing else.

The file below is a **historical changelog** of schema changes made so far, kept as a
paper trail. The original executable Alembic-style revision scripts were removed because
they were never wired up (no `alembic.ini` / `env.py`) and looked runnable when they
were not. If/when Alembic is adopted, generate a fresh baseline from the current models
rather than replaying these entries.

| # | Change | Details |
|---|--------|---------|
| 001 | Normalize `ingredients.season_months` | Convert free-text month values to a sorted, de-duplicated comma-separated list of month numbers (stored via the `IntList` TypeDecorator). |
| 002 | Add `recipe_ingredients` association table | Introduce a many-to-many `recipe_ingredients(recipe_id, ingredient_id, quantity, unit)` table; migrate the old inline `ingredients.recipe_id/quantity/unit` columns into it and drop them. |
| 003 | Add `recipes.course` | New non-null `course` column, default `"main"`. |
| 004 | Add `meals.side_recipe_id` | Nullable FK from `meals` to `recipes` for a single side dish. |
| 005 | Add `meal_side_dishes` table | Replace the single `meals.side_recipe_id` with an ordered `meal_side_dishes(plan_date, meal_number, position, side_recipe_id)` table (composite PK); migrate existing sides to `position = 1` and drop `meals.side_recipe_id`. |
| 006 | Add `meals.leftover` | New non-null boolean flag, default `false`. |
