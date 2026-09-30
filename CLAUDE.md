# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Meal Planner: a FastAPI + PostgreSQL backend that generates learning-based weekly meal plans, paired with a Vite/React frontend (`frontend-v2/`). The planner scores recipes on preference, seasonality, recency, tags, and bulk-prep, and uses ε-greedy exploration. See `README.md` for the full feature spec and `MEAL_PLANNER_DESIGN_GUIDE.md` for the mandatory UI conventions.

## Commands

### Backend (run from `backend/`)
```bash
pip install -r requirements.txt
uvicorn main:app --reload          # dev server (app is main:app, NOT app.main:app)
pytest                             # run all tests
pytest tests/test_planner.py       # single file
pytest tests/test_planner.py::test_name   # single test
flake8 .                           # lint (config in .flake8)
make lint / make test              # Makefile shortcuts
```
`pytest` needs a **disposable Postgres**: `tests/conftest.py` reads `TEST_DATABASE_URL` and forces
`DATABASE_URL` to it, so a real database can never win. Locally that is the `mp_test_pg` container
(`docker start mp_test_pg`); in CI it is a `postgres:16` service. The schema is dropped and rebuilt
per run, so never point it at anything you care about.

Note: the README's `app.main:app` and `python -m venv` snippets are stale — the app module is `main` at the backend root. CI (`.github/workflows/ci.yml`) runs `flake8 .` then `pytest` from `backend/` on Python 3.11.

### Frontend (run from `frontend-v2/`)
```bash
npm install
npm run dev        # Vite dev server on :3000
npm run test       # vitest (single run)
npm run lint       # eslint
npm run build
```
Set `VITE_API_BASE_URL` to point the frontend at the backend; otherwise requests are same-origin relative.

## Architecture

### One import root: top-level modules + the `mealplanner` package
There is a **single canonical set** of ORM models / db / crud, imported as the top-level modules `models`, `database`, and `crud` (run from `backend/`). The old `sys.modules` self-replacement shims (`mealplanner/models.py`, `db.py`, `crud.py`) have been **removed** — import `models` / `database` / `crud` directly. `mealplanner/*` code imports the canonical modules by top-level name (e.g. `from models import Recipe`).

The `mealplanner` package holds only the planner's *real* logic:
- `mealplanner/planner.py` — `generate_plan`, `generate_side_dish`, `filter_recipes`, and leftover "soft hold" scheduling.
- `mealplanner/scoring.py` — `score_recipe` and its components: base z-score/percentile squash,
  `seasonality_bonus`, `recency_penalty`, `bulk_bonus`, `tag_penalty`, `fridge_bonus`,
  `ingredient_repetition_penalty`, `tag_repetition_penalty` and `exploration_weight`.
- `mealplanner/config.py` — `DEFAULT_PLAN_SETTINGS` (leftover repeats, spacing, daypart prefs, etc.).
- `mealplanner/seed.py`, `mealplanner/utils.py`.

Tests import models/db/crud from the top-level modules and planner logic from `mealplanner.*` (see `tests/conftest.py`, which inserts the backend root onto `sys.path`). `mealplanner/` now lints under `flake8` (it is no longer excluded).

### Backend layers (all at `backend/` root)
- `main.py` — the app object, startup wiring, and **most** FastAPI routes. It is no longer the only route module: eight routers are pre-wired with `include_router` (`main.py:108-115`), so work on those domains does not serialise on this file: `username_routes.py`, `share_routes.py`, `public_pages.py`, `ops_routes.py`, `catalog_routes.py` (user-facing `/catalog/*`: browse, detail, batch adopt), `catalog_admin_routes.py` (`/admin/catalog/*`, every route behind `auth_users.require_admin`), `catalog_import_routes.py` (the admin reviewed-batch import) and `alpha_routes.py` (`/admin/alpha/*`, likewise admin-only — **temporary: closed-alpha scaffolding, removed with the alpha (`ALPHA-GATE`)**). Each router defines its own Pydantic models locally rather than adding them to `schemas.py`. `main.py` still holds recipes/ingredients/tags CRUD, meal-plan generate/set/get/delete, side-dish generation, accept/reject feedback, and data import/export.
- **Legacy `/plan` paths.** Three plan routes are double-registered as stacked decorators on a single
  handler, under legacy (`/plan`) and current (`/meal-plans`) paths: `GET` (`main.py:1251`), `POST`
  (`main.py:1263`) and `DELETE` (`main.py:1299`). **The legacy `/plan` paths are deprecated** — do
  not add new behaviour to them. They **cannot be removed yet**:
  `frontend-v2/src/api/mealPlansApi.js` still calls all three, so migrating that file is the real
  precondition for removal, not a date. Note that `/plan/settings` (GET/PUT, `main.py:1322` /
  `main.py:1332`) is **not** legacy — it has no `/meal-plans` twin and is the current path.
- `crud.py` — DB operations backed directly by the `meals` / `meal_plans` tables, which are the **single source of truth** for plans. (An earlier process-global in-memory cache `_PLAN_CACHE` / `_PLAN_SETTINGS` has been removed; see `list_planned_titles`'s comment noting it "replaces the former in-memory `_PLAN_CACHE`".)
- `models.py` — SQLAlchemy models. Plan tables are keyed by owner: `Meal` has composite PK
  `(user_id, plan_date, meal_number)` with a named `CHECK meal_number IN (1,2)`, `MealPlan` is
  `(user_id, plan_date)` and `MealSide` `(user_id, plan_date, meal_number, position)`. Constraints
  are **named explicitly**: an unnamed one has no name in the metadata to match the reflected one
  against, so autogenerate reads it as absent from the models and proposes dropping it on every
  migration. `IntList` TypeDecorator stores `list[int]` (e.g. `season_months`) as comma-separated
  strings. `MealSide` holds ordered side dishes per meal.
- `catalog.py` — all domain logic of the system recipe catalog ("Discover"): the `is_system` account (resolved by the flag, never by its `mealplanner` handle), listing, adoption counts, batch adopt, publish/retire, admin authoring, export, and `populate_from_pack`, which `main._bootstrap` runs to load `data/catalog_pack.json` into an empty catalog. It must not import `main` or any router (guarded by `tests/test_architecture_guards.py`). `User.is_admin` is **granted by direct SQL only** — no route, service or startup path ever writes it.
- `alpha.py` — the closed alpha's signup allowlist: normalization, free-text splitting, the
  `assert_email_allowed` gate (which **fails open on an empty table**) and the invite CRUD behind
  `alpha_routes.py`. **Temporary — closed-alpha scaffolding, removed with the alpha
  (`ALPHA-GATE`).** Every artefact carries that marker and all dependency arrows point *into* the
  feature, so removal is `git grep ALPHA-GATE` plus a drop-table revision; it imports only
  `models` (guarded by `tests/test_architecture_guards.py`).
- `schemas.py` — Pydantic request/response models.
- `database.py` — engine + `SessionLocal` + `Base`. The database is **PostgreSQL only**; `resolve_database_url()` reads the required `DATABASE_URL` env var (normalizing a bare `postgres://` scheme) and raises `RuntimeError` when it is unset — there is no fallback, so a misconfigured deploy fails loudly instead of silently using the wrong database.

### Auth & tenancy
**Every per-user row is owned, and every query must be scoped.** Ownership is declared uniformly by
`models._owner_fk_column()`, which puts a `user_id` FK on `Recipe`, `Ingredient`, `Tag`, `MealPlan`,
`Meal`, `MealSide`, `RecipeShare`, `RefreshToken`, `CatalogImportBatch` and `AlphaInvite`. Names are
unique *per owner*, not globally (`uq_ingredient_user_name`, `uq_tag_user_name`).

Scoping goes through `scoping.py` -- `scope(query, column, user_id)` for queries and `owned(obj,
user_id)` for loaded objects -- so "was this scoped?" is answerable by grep rather than by reading
every query. `user_id=None` means *no scoping*: a deliberate opt-out for low-level tests, never for a
request path. Routes always pass `current_user.id`. **A query you add without `scope()` leaks one
user's data to another** -- `crud.py`, `catalog.py`, `catalog_import.py` and `mealplanner/planner.py`
all route through it.

`auth_users.py` owns identity: bcrypt passwords, JWT access + refresh tokens (refresh `jti`s are
stored in `refresh_tokens` so they can be revoked on logout), Google sign-in, and email
verification / password-reset tokens. Routes take the caller via the `CurrentUser` dependency
(`main.py:265`, `Annotated[models.User, Depends(auth_users.get_current_user)]`) and admin-only routes
add `auth_users.require_admin` -- enforced on every route in `catalog_admin_routes.py`,
`catalog_import_routes.py` and `alpha_routes.py`. `ops_routes.py` is the deliberate exception: it
serves only `GET /health`, which the platform healthcheck must reach unauthenticated.

### Migrations
The schema is owned by **Alembic**. `alembic upgrade head` runs as the Railway `api` service's
**pre-deploy command, configured in the Railway dashboard** -- deliberately not in a `railway.json`,
which was deleted in `e5c67eb` so service settings stay dashboard-editable. It is therefore recorded
in **no file in this repo**, and running the image anywhere else migrates nothing: do that yourself
with `alembic upgrade head` from `backend/`. (Railway also builds the api service with the
**RAILPACK** builder, not `backend/Dockerfile` -- that Dockerfile serves `docker-compose` only, and
its own comment pointing at a `railway.json` is stale.)

The app does **not** call `Base.metadata.create_all` -- `create_all` only creates *missing* tables
and never alters existing ones, which silently loses schema changes against a populated database.
The one remaining call is in `scripts/seed_testing_data.py`, which rebuilds a throwaway schema from
scratch.

**Any model change needs a revision in the same commit:** `alembic revision --autogenerate -m "..."`
from `backend/`, then *read the generated script* (autogenerate cannot see renames and does not compare
`CHECK` expressions; data migrations are hand-written). `tests/test_migrations.py` builds a database
from the migrations alone and fails if it disagrees with the models, so drift is caught in CI.

Config is `backend/alembic.ini`; the URL is not in it -- `migrations/env.py` resolves it via
`database.resolve_database_url()` so migrations and app can never target different databases.
Generated revision scripts under `migrations/versions/` are excluded from `flake8`; `migrations/env.py`
is hand-written and is linted. `backend/migrations/README.md` documents the workflow and keeps the
pre-Alembic changelog as a historical paper trail.

### Testing data seed
`backend/scripts/seed_testing_data.py` performs a **complete DB reset** (drops + recreates every table).
It refuses to run unless `ALLOW_DESTRUCTIVE_SEED=1` -- it would otherwise wipe whatever `DATABASE_URL`
points at, including a deployment. `docker-compose.yml` sets the flag; no deployment may. The script inserts a coherent testing dataset (≥40 recipes, ≥50 ingredients, ≥10 tags). `docker-compose.yml` runs it before uvicorn, so **every `docker compose up` (built or not) starts from a clean, fully-populated database**. Run it manually with `python scripts/seed_testing_data.py` from `backend/`.

**MANDATORY:** whenever the database schema or domain model changes (new/renamed/removed columns, tables, enums, relationships, or constraints), `seed_testing_data.py` MUST be updated in the same change so the seeded data stays coherent with the updated database. A schema change is not complete until the seed script inserts valid data again.

### Frontend (`frontend-v2/src/`)
- `api/` — one module per resource (`recipesApi`, `mealPlansApi`, `ingredientsApi`, etc.); all go through `api/client.js`'s `request()` helper, which unwraps FastAPI's `{detail}` errors and returns `null` on 204.
- `pages/` — all routed in `App.jsx`. Core: `RecipesPage`, `MealPlanPage`, `IngredientsPage`,
  `ShoppingListPage`, `ImportExportPage`. Catalog: `DiscoverPage` (browsing and adopting from the
  recipe library at `/discover`), `CatalogAdminPage` (curating that library, at the same `/discover`),
  `SystemVocabularyPage`, `CatalogImportPage`, `CatalogImportReviewPage`. Auth: `LoginPage`,
  `ForgotPasswordPage`, `ResetPasswordPage`, `VerifyEmailPage`, `ChooseHandlePage`. Sharing:
  `SharedRecipePage`, `SharedWithMePage`. Plus `AlphaPage` (the closed-alpha invite list at
  `/discover/alpha` — **temporary, removed with the alpha (`ALPHA-GATE`)**).
- **User vs admin view.** An admin account wears one hat at a time. `auth/ViewModeContext.jsx` holds the mode (`useViewMode()` → `{ mode, isAdminMode, canAdmin, setMode }`); it is React state only, so every reload and sign-in starts in user mode, and it fails closed — `isAdminMode` re-reads `is_admin` on every render. `components/ViewModePill.jsx` is the header switch, rendered only for an admin, and it navigates (`/discover` into admin, `/recipes` out). In admin mode `Sidebar` lists Discover, Ingredients & Tags (`/discover/vocabulary`) and Import (`/discover/import`, with the review page at `/discover/import/:batchId`); `/discover` renders `CatalogAdminPage`. Those admin-only routes are gated by `AdminOnlyRoute` in `App.jsx`, which redirects to `/discover` outside admin mode; every other route stays reachable by URL. **The mode is presentation, never permission** — the server enforces admin with `require_admin` on every `/admin/catalog/*` route. In user mode an admin's screens are byte-for-byte a normal user's.
- `components/` — shared primitives (`Button`, `Card`, `Badge`, modals, seasonality/month grids), re-exported from `components/index.js`.
- Styling is Tailwind + CSS variables from the design guide (`--c-pos: #0C3A2D`, `--c-neg: #BD210F`, etc.). All UI work must follow `MEAL_PLANNER_DESIGN_GUIDE.md`.

## Scoring & planner notes
- Only `main` and `first-course` recipes are candidates for main slots; `side` recipes are drawn separately via `generate_side_dish`.
- Leftovers use a "soft hold": when a `bulk_prep` recipe is accepted, future slots within `keep_days` are reserved (respecting `LEFTOVER_SPACING_GAP`, `MAX_LEFTOVERS_PER_DAY`, and daypart prefs), and its recency penalty is zeroed in held slots.
- `scoring.py` uses hardcoded tunables (`RECENCY_WINDOW_DAYS = 15.0`, `HALF_LIFE_DAYS = 4.0`) — behavior is intentionally deterministic for unit testing.
- A meal is a leftover exactly when it links back to the meal that produced it, via
  `leftover_source_date` / `leftover_source_meal`, kept all-or-nothing by
  `ck_meal_leftover_source_all_or_nothing`. `Meal.leftover` is a **derived property**, not a stored
  column — the old `" (leftover)"` title-suffix encoding is gone, so do not reintroduce string
  parsing of recipe titles.

## Conventions
- `flake8` excludes `tests/` and `migrations/versions/` (the `mealplanner/` package is linted); max line length 120. New backend code outside the excluded dirs must lint clean.
- Backend commands assume the working directory is `backend/` (imports are top-level, not package-qualified from the repo root).

## Plans 
- when developing a plan require to use the /test-driven-development to implement it. Create each plan following the test driven development rules
-the last step of each plan has to run the /simplify skill

## Instruction 
- ask all the questions needed to correctly understand the scope of changes don't assume any user decision 
- call me sir when adressing me.