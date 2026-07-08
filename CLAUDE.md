# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Meal Planner: a FastAPI + SQLite backend that generates learning-based weekly meal plans, paired with a Vite/React frontend (`frontend-v2/`). The planner scores recipes on preference, seasonality, recency, tags, and bulk-prep, and uses ε-greedy exploration. See `README.md` for the full feature spec and `MEAL_PLANNER_DESIGN_GUIDE.md` for the mandatory UI conventions.

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
- `mealplanner/scoring.py` — `score_recipe` and its components (base z-score/percentile squash, seasonality, recency decay, bulk bonus, tag penalty).
- `mealplanner/config.py` — `DEFAULT_PLAN_SETTINGS` (leftover repeats, spacing, daypart prefs, etc.).
- `mealplanner/seed.py`, `mealplanner/utils.py`.

Tests import models/db/crud from the top-level modules and planner logic from `mealplanner.*` (see `tests/conftest.py`, which inserts the backend root onto `sys.path`). `mealplanner/` now lints under `flake8` (it is no longer excluded).

### Backend layers (all at `backend/` root)
- `main.py` — every FastAPI route. Recipes/ingredients/tags CRUD, meal-plan generate/set/get/delete, side-dish generation, accept/reject feedback, and data import/export. Routes are double-registered under legacy (`/plan`) and current (`/meal-plans`) paths. **The legacy `/plan` routes are deprecated** (kept for backward compatibility only) — prefer `/meal-plans`. Removal is scheduled no earlier than **2026-10-01**; do not add new features to the `/plan` paths.
- `crud.py` — DB operations backed directly by the `meals` / `meal_plans` tables, which are the **single source of truth** for plans. (An earlier process-global in-memory cache `_PLAN_CACHE` / `_PLAN_SETTINGS` has been removed; see `list_planned_titles`'s comment noting it "replaces the former in-memory `_PLAN_CACHE`".)
- `models.py` — SQLAlchemy models. `Meal` has composite PK `(plan_date, meal_number)` with a `CHECK meal_number IN (1,2)`. `IntList` TypeDecorator stores `list[int]` (e.g. `season_months`) as comma-separated strings. `MealSide` holds ordered side dishes per meal.
- `schemas.py` — Pydantic request/response models.
- `database.py` — engine + `SessionLocal` + `Base`; SQLite file at `backend/data/app.db` (absolute path derived from the module location). `main.py` calls `Base.metadata.create_all` on startup, so a fresh DB needs no migration step.

### Migrations
**The real schema story is `Base.metadata.create_all` on startup** (`main.py`), so a fresh DB needs no migration step. There is **no active migration system** and `alembic` is not a dependency. During development, changing the schema means changing the model and starting against a fresh DB — nothing else. Real migrations will be adopted via `alembic init` (generating a fresh baseline from the models) when the project approaches production and must evolve a populated DB in place. `backend/migrations/README.md` holds a historical changelog of past schema changes; do **not** add new revision scripts.

### Testing data seed
`backend/scripts/seed_testing_data.py` performs a **complete DB reset** (drops + recreates every table) and inserts a coherent testing dataset (≥40 recipes, ≥50 ingredients, ≥10 tags). `docker-compose.yml` runs it before uvicorn, so **every `docker compose up` (built or not) starts from a clean, fully-populated database**. Run it manually with `python scripts/seed_testing_data.py` from `backend/`.

**MANDATORY:** whenever the database schema or domain model changes (new/renamed/removed columns, tables, enums, relationships, or constraints), `seed_testing_data.py` MUST be updated in the same change so the seeded data stays coherent with the updated database. A schema change is not complete until the seed script inserts valid data again.

### Frontend (`frontend-v2/src/`)
- `api/` — one module per resource (`recipesApi`, `mealPlansApi`, `ingredientsApi`, etc.); all go through `api/client.js`'s `request()` helper, which unwraps FastAPI's `{detail}` errors and returns `null` on 204.
- `pages/` — `RecipesPage`, `MealPlanPage`, `IngredientsPage`, `ShoppingListPage`, `ImportExportPage`, routed in `App.jsx`.
- `components/` — shared primitives (`Button`, `Card`, `Badge`, modals, seasonality/month grids), re-exported from `components/index.js`.
- Styling is Tailwind + CSS variables from the design guide (`--c-pos: #0C3A2D`, `--c-neg: #BD210F`, etc.). All UI work must follow `MEAL_PLANNER_DESIGN_GUIDE.md`.

## Scoring & planner notes
- Only `main` and `first-course` recipes are candidates for main slots; `side` recipes are drawn separately via `generate_side_dish`.
- Leftovers use a "soft hold": when a `bulk_prep` recipe is accepted, future slots within `keep_days` are reserved (respecting `LEFTOVER_SPACING_GAP`, `MAX_LEFTOVERS_PER_DAY`, and daypart prefs), and its recency penalty is zeroed in held slots.
- `recency`/`seasonality` in `scoring.py` contain `print()` debug statements and hardcoded tunables (`RECENCY_WINDOW_DAYS`, `HALF_LIFE_DAYS`) — behavior is intentionally deterministic for unit testing.
- Leftover titles are encoded by suffixing `" (leftover)"` on the recipe title string; `main.py` parses this suffix back out.

## Conventions
- `flake8` excludes `pages/` and `tests/` (the `mealplanner/` package is now linted); max line length 120. New backend code outside the excluded dirs must lint clean.
- Backend commands assume the working directory is `backend/` (imports are top-level, not package-qualified from the repo root).

## Plans 
- when developing a plan require to use the /test-driven-development to implement it. Create each plan following the test driven development rules
-the last step of each plan has to run the /simplify skill

## Instruction 

- call me sir when adressing me.