# Migrations

This project uses **Alembic**. The deployed schema is defined by the revision
scripts in `versions/`, and `alembic upgrade head` runs at container start
(`backend/Dockerfile`) -- so a failed migration fails the deploy rather than
producing a service whose code expects columns the database does not have.

The app does **not** create its own tables. `Base.metadata.create_all` only ever
creates what is *missing*; it never alters an existing table, which is fine for a
disposable development database and silently wrong for one holding real data.

## Changing the schema

1. Change the model in `models.py`.
2. `alembic revision --autogenerate -m "what changed"` (run from `backend/`,
   with `DATABASE_URL` pointing at a database that is already at `head`).
3. **Read the generated script.** Autogenerate is a first draft: it does not
   detect renames (it sees a drop plus an add, which loses the data), and it
   does not compare `CHECK` constraint expressions. Data migrations are always
   hand-written.
4. Update `scripts/seed_testing_data.py` in the same change -- CLAUDE.md makes
   that part of any schema change.
5. `tests/test_migrations.py` builds a database from the migrations alone and
   fails if it does not match the models. A model change with no revision behind
   it is caught there.

Configuration lives in `backend/alembic.ini`, but the database URL does not:
`migrations/env.py` resolves it through `database.resolve_database_url()`, the
same function the app uses, so the migrations and the app can never be pointed at
two different databases.

## Rolling back

`alembic downgrade -1`. Downgrades are generated but rarely exercised -- on a
database with real data, restoring the platform's backup is usually both safer
and faster.

## Alembic revisions

A one-line changelog of revisions, newest first. The revision script's own
docstring is the full record; this table is for finding the right one.

| Revision | Change | Details |
|----------|--------|---------|
| `67f3715acf44` | System recipe catalog | Adds `catalog_entries` (`recipe_id` PK → `recipes.id` `ON DELETE CASCADE`, `status`, `published_at`, `retired_at`) with the named CHECKs `ck_catalog_entry_status` and `ck_catalog_entry_retired_all_or_nothing`; `ix_recipes_source_recipe_id`; `users.is_system` and `users.is_admin` (NOT NULL, default false); the unique partial index `uq_user_single_system` (`WHERE is_system`). Schema only -- the catalog's data is loaded at startup, not by the migration. |

## Historical changelog (pre-Alembic)

Everything below predates the migration system. It is a paper trail, not
something to run: the baseline revision in `versions/` was generated fresh from
the models and already contains the cumulative result of every entry here.

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
> TEXT` â†' backfill from the email local part (sanitised to `^[a-z0-9_]{3,30}$`
> and disambiguated with a numeric suffix, as `crud._derive_username` does) â†'
> `CREATE UNIQUE INDEX uq_user_username_lower ON users (lower(username))` â†'
> `ALTER COLUMN username SET NOT NULL`. The remaining columns are all nullable
> or defaulted and can be added in place.
