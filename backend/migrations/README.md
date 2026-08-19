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
| 007 | Recipe sharing, Part 1 | **Requires a fresh database.** Adds `users.username` (NOT NULL, case-insensitively unique via the functional index `uq_user_username_lower`) and `users.username_changed_at`; adds `recipes.visibility` (NOT NULL, `DEFAULT 'private'`), `page_layout`, `page_theme`, `copy_count`, `source_recipe_id`, `source_user_id`, `source_author_username`, `source_recipe_title`, `copied_at`; adds the `recipe_shares` and `reserved_usernames` tables. |

> **Release note for 007.** `Base.metadata.create_all` never `ALTER`s an existing
> table, and a NOT NULL unique `users.username` is unreachable on a populated one.
> Per the project's development story this release therefore **requires a fresh
> database**: drop and recreate, or re-run `scripts/seed_testing_data.py`.
>
> If a deployed environment holds data worth keeping, a one-off SQL script is
> required and is deliberately **not** part of this change: `ADD COLUMN username
> TEXT` → backfill from the email local part (sanitised to `^[a-z0-9_]{3,30}$`
> and disambiguated with a numeric suffix, as `crud._derive_username` does) →
> `CREATE UNIQUE INDEX uq_user_username_lower ON users (lower(username))` →
> `ALTER COLUMN username SET NOT NULL`. The remaining columns are all nullable
> or defaulted and can be added in place.
