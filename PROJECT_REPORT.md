# Meal Planner — Project State & Architecture Report

_Generated 2026-07-06. Covers the backend (`backend/`) and frontend (`frontend-v2/`)._

---

## Part 1 — Where the project is right now

### What it is
A **learning-based weekly meal planner**. A FastAPI + PostgreSQL backend generates meal
plans by scoring recipes; a Vite/React (React 19) frontend drives the UI. The planner
scores each recipe on preference, seasonality, recency, tags and bulk-prep, and uses
ε-greedy exploration to occasionally pick non-optimal recipes so the user's taste model
keeps learning.

### What it does today (working features)
- **Recipe CRUD** with tags (many-to-many), ingredients (with `season_months`), a
  `course` field (`main` / `first-course` / `side`), servings, procedure and a
  `bulk_prep` flag.
- **Ingredient CRUD** with search, per-ingredient season months, and a "recipes using
  this ingredient" lookup + safe/forced delete.
- **Meal-plan generation** over a date range (`/meal-plans/generate`) with tunable
  weights, ε, avoid/reduce tags, and a **leftover "soft-hold"** scheduler that reserves
  future slots for bulk-prep recipes within a `keep_days` window.
- **Plan persistence**: get/set/delete plans, with a **409 conflict flow** when
  overwriting existing days (frontend has an overwrite-confirm modal).
- **Accept / reject feedback** that adjusts a recipe's `score` and `date_last_consumed`;
  reject suggests a random replacement.
- **Side-dish generation** and per-meal side management (add/replace/remove, ordered).
- **Data import/export** (JSON) with `overwrite` / `merge` modes, plus a `DELETE /data`
  wipe.
- **Frontend pages**: Recipes (with course + filter), MealPlan (the big one), Ingredients,
  ShoppingList, ImportExport.

### Test / build health
- Backend: **103 tests pass**. One test file (`test_migration_course.py`) **fails to
  collect** because `alembic` isn't importable in the current env (it's listed in
  `requirements.txt` but the local venv doesn't have it installed).
- CI runs `flake8 .` then `pytest` on **Python 3.11**; local machine is on **3.13**.
- Pydantic emits **deprecation warnings** everywhere — schemas still use v1-style
  `class Config: orm_mode = True` (v2 wants `model_config = ConfigDict(from_attributes=True)`).

### The last chunk of work (recent commits)
The recent history is almost entirely **meal-plan lifecycle and leftover fixes**:
1. `79a99c0` fix leftover scheduling
2. `2c14dd0` fix leftover flag when rejecting meals
3. `#293` extend meal-plans API + update MealPlanPage
4. `#294 / #295` **delete meal plans** feature (backend helper + API + legacy route)
5. `3f33b45` overwrite-confirm modal on generation
6. Several PRs reworking **date handling / days-range** for generation (start+end dates,
   day count, decoupling calendar view from plan range).
7. `144712d` tweaked the default ε value.

**Takeaway:** the plan-generation + leftovers + date-range flow was the active battlefield
and has been stabilized. That's your current "frontier."

---

## Part 2 — Architectural issues to fix before building further

Ordered roughly by how much they'll hurt you. The 🔴 items I'd fix before adding features.

### 🔴 Security

1. **No authentication or authorization of any kind.** Every endpoint is open, including
   `DELETE /data` (wipes the entire database) and `POST /data/import` (replaces it). If
   this is ever exposed beyond localhost it's a one-request data-loss vulnerability. Add
   at least an API key / auth layer before any deployment.
   - `backend/main.py:456` (`DELETE /data`), `:443` (`import`).

2. **CORS is wide open _and_ misconfigured.** [main.py:28-34](backend/main.py#L28-L34)
   sets `allow_origins=["*"]` together with `allow_credentials=True`. That combination is
   rejected by browsers and is a security smell — lock origins to the real frontend URL.

3. ~~**The SQLite database is committed to git.**~~ ✅ **Resolved.** The file was
   untracked and gitignored, and SQLite has since been removed entirely: the app is
   PostgreSQL-only and `DATABASE_URL` is required, with no local-file fallback.

### 🔴 Correctness bugs hiding in the planner/scoring core

4. **Season filtering in the planner is dead code.**
   [planner.py:337](backend/mealplanner/planner.py#L337) reads
   `getattr(recipe, "recipe_ingredients", [])` — but the ORM relationship is named
   **`ingredients`**, not `recipe_ingredients`. So the list is always empty and the
   `if season is not None and recipe_ingredients and ...` guard **always short-circuits**:
   recipes are never filtered by season. Seasonality only survives as a soft scoring bonus.
   This is a genuine "silently does nothing" bug.

5. **`recency_penalty` contradicts its own contract and constants.**
   [scoring.py:45-64](backend/mealplanner/scoring.py#L45-L64):
   - The docstring says "penalty starts at -10", but `RECENCY_MAX_PENALTY = 30`.
   - Doc comments say "after 30 days no penalty / halves every 7 days" while constants are
     `RECENCY_WINDOW_DAYS = 15` and `HALF_LIFE_DAYS = 4`.
   - It does `days = abs(days)`, so a recipe planned in the *future* is penalized as if in
     the past.
   These are all deterministic tunables masquerading as documented behavior — anyone
   tuning the algorithm will be misled.

6. **`seasonality_bonus` penalizes hard and prints to stdout.**
   [scoring.py:94-97](backend/mealplanner/scoring.py#L94-L97) does `in_season -= 2` for
   out-of-season ingredients and `print("it is in season")`. Combined with #4 this is the
   *only* place seasonality acts, and its magnitude (`10 * net / len`) is undocumented.

7. **Debug `print()` statements ship in the hot path.** 4 prints in `mealplanner/`,
   including per-recipe ANSI-colored logging inside the generation loop
   ([planner.py:116-131](backend/mealplanner/planner.py#L116-L131)). Replace with a real
   logger at DEBUG level. CLAUDE.md even acknowledges these as intentional — they should
   move behind logging.

### 🟠 Architecture / maintainability

8. **The `mealplanner` package is a `sys.modules` self-replacement shim.**
   `mealplanner/models.py`, `db.py`, `crud.py` swap themselves out for the root-level
   modules so both `import models` and `import mealplanner.models` resolve to the same
   objects. It works, but it's a foot-gun: import order matters, tooling gets confused, and
   `flake8` has to *exclude* `mealplanner/`. Long term, pick **one** import root (make the
   backend a real package, e.g. `app/`) and delete the shims.

9. **Stale project documentation.** `CLAUDE.md` still describes a process-global
   `_PLAN_CACHE` / `_PLAN_SETTINGS` in `crud.py` as "a key gotcha" — that cache has been
   **removed** (see `list_planned_titles`'s own comment: "replaces the former in-memory
   `_PLAN_CACHE`"; the DB is now the single source of truth). The README also documents
   stale run commands (`app.main:app`). Docs are drifting from reality.

10. **Migrations are half-wired.** `backend/migrations/00X_*.py` are Alembic-style revision
    files, but there's **no committed `alembic.ini` / `env.py`**, so `alembic upgrade head`
    can't actually run. Schema is created ad-hoc via `Base.metadata.create_all` on startup.
    That's fine for a fresh DB but means **you have no real migration path for existing
    data** — any schema change to a populated DB is manual. Either commit a working Alembic
    config or drop the pretense and document the create_all approach.

11. **Import logic in `crud.import_data` is large and duplicated.**
    [crud.py:667-714](backend/crud.py#L667-L714): the "merge" and both "overwrite" branches
    build a `Recipe` with the *same* field list three times. The `existing`-vs-new overwrite
    branch produces an identical object either way. Ripe for the `/simplify` pass.

12. **`MealPlanPage.jsx` is 778 lines.** It's by far the largest frontend file and the one
    every recent PR has touched (date handling, generation, overwrite modal, deletion).
    It's becoming a merge-conflict magnet. Extract the generation flow, calendar view, and
    plan-state reducer into hooks/subcomponents.

13. **Two stores that "must be kept consistent" per the design.** Meals are persisted in
    the `meals`/`meal_plans` tables while leftover titles are encoded by suffixing
    `" (leftover)"` onto the title string and parsed back in `main.py`
    ([main.py:402-403](backend/main.py#L402-L403)). Encoding domain state in a display
    string is fragile — any recipe literally named "... (leftover)" breaks it. Prefer the
    boolean `leftover` column that already exists on `Meal`.

### 🟡 Smaller cleanups

14. **`crud.get_recipes()` ([crud.py:270](backend/crud.py#L270)) references a
    `tests.test_app` stub** that no longer appears to exist — likely dead code.
15. **Duplicate route registration** (`/plan` legacy + `/meal-plans`) doubles the surface
    to maintain and test. Pick a deprecation date for the legacy paths.
16. **Inconsistent asset naming** in `frontend-v2/public/assets/icons/` — both
    `left overs icon.png` (with spaces) and `left_overs_icon.png` exist.
17. **`bulk_bonus` / `tag_penalty` magic numbers** (10, 3) are inline literals, not config.
18. Pydantic v1→v2 migration (`orm_mode` → `from_attributes`) to silence deprecation and
    future-proof against Pydantic v3.

---

## Recommended order of attack for a "solid ground"

1. **Stop the bleeding (½ day):** ~~untrack `app.db`~~ (done — SQLite is gone), add auth
   or bind to localhost, fix CORS.
2. **Fix the silent planner bugs (#4, #5, #6):** these change actual output — do them
   test-first so you lock in the intended seasonality/recency behavior.
3. **Replace prints with logging (#7)** and reconcile the docstrings/constants.
4. **De-shim the package (#8)** and update `CLAUDE.md` + README (#9) so the docs match code.
5. **Decide the migration story (#10).**
6. **Refactor `MealPlanPage.jsx` (#12)** and `import_data` (#11) once the above is stable.

Items 1–3 are the ones that make the difference between "looks like it works" and
"actually does what the spec says."
