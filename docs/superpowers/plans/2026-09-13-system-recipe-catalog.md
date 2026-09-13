# System Recipe Catalog ("Discover") — Parallel Implementation Plan

**Spec:** `docs/superpowers/specs/2026-09-12-system-recipe-catalog-design.md` (every requirement ID below — SYS-, DM-, CAT-, ADO-, API-, UI-, RM-, SEED-, TST- — refers to it).
**Branch:** `feature/system-recipe-catalog` (integration branch). No push, no PR unless the user asks.

---

## Context

A new account today starts with an empty recipe book. Its only source of recipes is a 1416-line
client-side starter pack (`frontend-v2/src/constants/starterRecipes.js` + `StarterRecipesModal.jsx`).
That pack is reachable only while the book is empty, stores no provenance, needs a frontend deploy
to change, and adds recipes with 60 serial `POST /recipes` calls.

The spec moves the pack server-side as a curatable **catalog** with these properties:
- it is owned by an `is_system` account, with membership in `catalog_entries`
- it is ranked by distinct adopters, derived from `source_recipe_id`
- users browse it at `/discover` and add recipes with a one-transaction batch adopt
- admins curate it through an admin UI (`is_admin`, granted by SQL only)

It also deletes the starter pack. Most of the machinery already exists from Part 1 sharing: `recipe_copy`,
the attribution snapshot, `ratelimit.limiter`, and the domain-router pattern.

## Decisions taken with the user (binding — do not re-open)

| # | Decision |
|---|---|
| D1 | **Parallelism:** every parallel agent runs in its own **git worktree** on a task sub-branch and uses its **own Postgres test database**. Only T1 and the orchestrator's integration steps run `tests/test_migrations.py`, because its scratch DB name is fixed. |
| D2 | **bulk_prep:** `recipe_copy.duplicate()` gains `bulk_prep` in its allowlist. This fixes adoption and user-to-user share copies alike. Both paths get tests. |
| D3 | **Admin form:** reuse `NewRecipeModal` with injectable ingredient and tag sources. Add two read-only admin routes, `GET /admin/catalog/ingredients` and `GET /admin/catalog/tags`, which return the system account's rows. New-ingredient creation is disabled in catalog mode. The server resolves names in the system namespace and **rejects unknown ingredient or tag names with 400**. This adds routes beyond spec §10.2, with the user's written approval. |
| D4 | **Three user-testing pauses:** P1 user-facing Discover + adopt + starter removal; P2 admin curation; P3 final sweep + `/simplify`. |
| D5 | **Skills:** do **not** use superpowers executor or planning skills (`subagent-driven-development`, `executing-plans`, `writing-plans`). The orchestrator dispatches agents as written here. **Every implementing agent MUST invoke `superpowers:test-driven-development`** (CLAUDE.md) and work red → green → refactor. `/simplify` is the last step. |
| D6 | **Test data:** follow SEED-3. `docker compose up` shows the seed script's catalog, not the 60-recipe pack. The pack is proven by tests and by the fresh-DB check at P3. |
| D7 | **System handle:** keep ADO-8 literally, so copies store `source_author_username='mealplanner'`. Mask it on output: `RecipeOut` returns `source_author_username = None` whenever `from_library` is true. **Accepted residual:** a user who shares an adopted copy by link exposes the handle in that share page's JSON-LD (`public_schema.py:80`), which P2-5 forbids changing. Record this in the P3 report. |

---

## Execution model (read first — applies to every task)

### Orchestrator (the main session)
1. Copy this plan to `docs/superpowers/plans/2026-09-13-system-recipe-catalog.md` and commit it on `feature/system-recipe-catalog` before dispatching anything, so every worktree contains it.
2. Dispatch each task with `Agent` (`subagent_type: "general-purpose"`, `isolation: "worktree"`, `run_in_background: true`). The prompt comes from the template below. Start a task as soon as **all its dependencies are merged**. Do not wait for unrelated tasks.
3. When a task reports done:
   - read its report
   - `git merge --no-ff <task-branch>` into `feature/system-recipe-catalog`
   - resolve any conflict, keeping both sides' intent
   - run the **merge gate**: the full backend suite on the default `mealsdb_test` including `test_migrations.py`, `python -m flake8 .`, and `npm run test && npm run lint` if frontend files changed
   - fix the break or send it back to the agent if red
4. Dispatch the next unblocked tasks from the new HEAD, so each worktree branches from a tree containing its dependencies.
5. At a **PAUSE**, stop dispatching. Run the pause's gate, then present its manual test checklist to the user and **wait for the user's go-ahead**.

### Agent prompt template
> You are implementing **Task Tn** of `docs/superpowers/plans/2026-09-13-system-recipe-catalog.md` in your own git worktree. Read the plan's "Execution model", "Contracts" and your task section, and the spec sections it cites. Invoke the `superpowers:test-driven-development` skill and follow it: write each listed test first, watch it fail, then implement. Edit **only** the files your task owns; if you need a change elsewhere, stop and report it instead. Use your own test database as described under "Per-agent environment". Commit on your worktree branch with focused commits ending in `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`. Do not push. Finish with a report: branch name, files changed, the verification commands you ran with their pass/fail output, and any deviation or open question.

### Per-agent environment (PowerShell; shell state does not persist, so set env vars in the same command)
- **Backend**, from `<worktree>/backend`, with `<db>` = `mealsdb_test_<task id>` (e.g. `mealsdb_test_t5`):
  ```powershell
  docker start mp_test_pg
  docker exec mp_test_pg psql -U user -d postgres -c "CREATE DATABASE <db>;"   # once; ignore 'already exists'
  $env:TEST_DATABASE_URL='postgresql://user:pass@localhost:5432/<db>'; python -m pytest --ignore=tests/test_migrations.py
  python -m flake8 .
  ```
  Only T1 may run `tests/test_migrations.py` itself.
- **Frontend**, from `<worktree>/frontend-v2`: `npm ci` once, then `npm run test` and `npm run lint`.
- The pytest import runs `main._bootstrap()`, which from T8 onward loads 60 catalog recipes into the test DB. Catalog tests **must** use the `system_account` fixture (T1), which clears catalog entries inside the test's rolled-back transaction. They must never assert on global counts they did not create.

---

## Contracts (frozen — parallel tasks build against these)

### Backend service — `backend/catalog.py`
| Symbol | Owner | Behaviour |
|---|---|---|
| `SYSTEM_ACCOUNT_USERNAME = "mealplanner"`, `SYSTEM_ACCOUNT_EMAIL = "mealplanner@localhost"` | T1 | Used **only** when creating the account (SYS-6). |
| `LISTING_CAP = 500`, `ADOPT_BATCH_MAX = 100` | T1 | API-20 cap; the comment says pagination is the next step. ADO-15 bound. |
| `class SystemAccountMissing(RuntimeError)` | T1 | CAT-3. |
| `class CatalogEntryNotFound(LookupError)`, `class IncompleteRecipe(ValueError)` | T1 | 404 / 400 (`str(e)` names the missing part). |
| `system_user(session) -> User` | T1 | Resolves `is_system = true`; raises `SystemAccountMissing`. |
| `ensure_system_account(session) -> User` | T1 | Get or create: `crud.create_user(email=…, username=…, hashed_password=None)`, then set `is_system=True` and `email_verified=False`, then `seed_system_tags` + `seed_system_ingredients` for it (SYS-3/5/8/10/12). Idempotent. |
| `list_published(session, *, course=None, tags=None, query=None, sort="popular") -> list[CatalogRow]` | T5 | `CatalogRow(recipe, adoption_count)`. Membership is **only** a `published` entry (P2-1/FC-1; no ownership filter). Course filter is OR; tags are AND; `q` is `ILIKE` with `%`, `_` and `\` escaped (ERR-11). `popular` sorts count desc then title asc; `title` sorts title asc. Eager-loads ingredients and tags with `selectinload` (CAT-5). Result is capped at `LISTING_CAP`. |
| `get_published(session, recipe_id) -> CatalogRow` | T5 | Raises `CatalogEntryNotFound` unless published (API-5). |
| `adoption_counts(session, recipe_ids) -> dict[int, int]` | T5 | One grouped `COUNT(DISTINCT user_id)`, excluding the system account (POP-1..4). |
| `held_by(session, user, recipe_ids) -> set[int]` | T5 | Source ids the user already holds a copy of, in one query (API-3). |
| `adopt(session, user, recipe_ids) -> AdoptResult(created_ids, skipped_ids)` | T5 | Rejects an empty list or more than `ADOPT_BATCH_MAX` ids with `ValueError`. Dedupes ids. Loads the published entries in one query and raises `CatalogEntryNotFound` if any is missing, with **no writes**. For each entry: `existing_copy` → skip; otherwise `recipe_copy.duplicate()` and `copy_count += 1`. **Exactly one `commit()`**, and rollback on any exception (ADO-2..16). `created_ids` are the new recipe ids. |
| `publish(session, recipe)` / `retire(session, recipe)` | T5 | Both **flush, never commit**; the caller commits (FC-5). `publish` does the CAT-9 check (a single commented block, FC-2) and CAT-10 → `IncompleteRecipe`, then covers CAT-6/7. `retire` covers CAT-8. Retiring a non-catalogued recipe raises `CatalogEntryNotFound`; retiring an already retired one is a no-op. |
| `populate_from_pack(session, path=PACK_PATH) -> int` | T8 | INIT-8..13 and EXP-5. Returns the number created. |
| `list_all`, `create_catalog_recipe`, `update_catalog_recipe`, `export_catalog`, `system_ingredients`, `system_tags` | T9 | §9, §10.2, D3. |

### User-facing HTTP — `backend/catalog_routes.py` (T7). All routes require auth.
```
GET  /catalog/recipes?course=main&course=side&tags=vegan&tags=quick&q=pasta&sort=popular|title
 -> 200 [ CatalogRow ]
    CatalogRow = { id, title, course, servings, bulk_prep, image_url,
                   tags: [str], ingredients: [{name, quantity, unit}],
                   adoption_count: int, in_my_book: bool }
GET  /catalog/recipes/{recipe_id}  -> 200 CatalogRow + { procedure }   | 404
POST /catalog/adopt  {"recipe_ids": [int]}
 -> 200 {"created_ids": [int], "skipped_ids": [int]}
    400 empty / > ADOPT_BATCH_MAX (message names the limit) | 404 any id not published | 429
```
`unit` ∈ `g|ml|piece`; `quantity` is written for `servings` people. Responses are built from explicit field allowlists and never from the ORM object (API-7/8). `SystemAccountMissing` → 500 with `logger.error("catalog: no is_system account …")` (ERR-5).

### Admin HTTP — `backend/catalog_admin_routes.py` (T9). Router-level `dependencies=[Depends(auth_users.require_admin)]`, prefix `/admin/catalog`.
```
GET  /recipes                  -> [ AdminRow ]  AdminRow = CatalogRow − in_my_book + {procedure, status, published_at, retired_at}
POST /recipes                  body RecipeWrite + {"publish": bool = true} -> 201 AdminRow
PUT  /recipes/{recipe_id}      body RecipeWrite -> 200 AdminRow | 404 if not a system-owned catalog recipe
POST /recipes/{recipe_id}/publish -> 200 AdminRow | 400 incomplete | 403 not system-owned | 404
POST /recipes/{recipe_id}/retire  -> 200 AdminRow | 404
GET  /export                   -> [ {title, course, servings, bulk_prep, tags:[str], procedure,
                                     ingredients:[{name,quantity,unit}], status, published_at, retired_at} ]
GET  /ingredients              -> [ {id, name, season_months, grams_per_ml, grams_per_piece, preferred_dimension} ]   (system account's)
GET  /tags                     -> [ {id, name} ]                                                                      (system account's)
RecipeWrite = {title, course, servings, bulk_prep, procedure, image_url?, tags:[str], ingredients:[{name, quantity, unit}]}
```
Non-admin → 403 `{"detail": "Forbidden"}`, identical for every path (PRV-5). Unauthenticated → 401. Unknown ingredient or tag name → 400 (D3). No DELETE route exists (API-14).

### Existing schemas (T1)
- `UserOut.is_admin: bool = False`.
- `RecipeOut.from_library: bool = False`. When it is true, `source_author_username` serialises as `None` (D7).

### Catalog pack file — `backend/data/catalog_pack.json` (T2)
A JSON **array** of `{title, course, servings, bulk_prep, tags:[str], procedure, ingredients:[{name, quantity, unit}]}`. `servings` is always explicit (default 1). Ingredient names use the **exact spelling** from `system_ingredients.json`. The export format is a superset of this.

### Frontend — `frontend-v2/src/api/catalogApi.js`
- **T3:** `catalogApi.list({courses, tags, q, sort})` uses `URLSearchParams.append` for repeatable keys. Also `catalogApi.get(id)` and `catalogApi.adopt(ids)`.
- **T10:** adds `catalogApi.admin = { list, create, update, publish, retire, exportCatalog, ingredients, tags }`.

Rows pass through unnormalised, like `sharedWithMeApi`. `recipesApi.normaliseRecipe` passes `from_library` through (T4).

---

## Dependency graph & waves

```
PHASE 1 ──────────────────────────────────────────────────────────────
 T1 Schema foundation [BE] ─┬─► T5 Catalog service [BE] ─┬─► T7 User routes [BE] ─┐
                            │                            └─► T8 Bootstrap pack [BE] ┤ (T8 also needs T2)
                            └─► T6 Seed scripts [BE] ───────────────────────────────┤
 T2 Pack port [data] ───────────────────────────────────────────────────────────────┤
 T3 Discover page [FE] ─────────────────────────────────────────────────────────────┤
 T4 Starter removal + attribution [FE] ─────────────────────────────────────────────┴─► I1 ═ PAUSE 1
PHASE 2 ──────────────────────────────────────────────────────────────
 T9 Admin service + routes [BE] ─┐
 T10 Admin UI [FE] ──────────────┴─► I2 ═ PAUSE 2
PHASE 3 ──────────────────────────────────────────────────────────────
 T11 DoD sweep + /simplify ─► PAUSE 3 (final)
```
Peak concurrency is 4 agents: T1, T2, T3 and T4 start together. T5 and T6 start when T1 merges, then T7 and T8 once their dependencies land.

**Shared-file rule:** `main.py` is edited by T7 (the `include_router` block) and T8 (`_bootstrap`), and later by T9 (`include_router`). These are separate hunks, so the orchestrator merges them. `tests/test_app_wiring.py` is owned by T7 in Phase 1 and T9 in Phase 2. `catalog.py` has exactly one owner at a time: T1 → T5 → T8 → T9.

---

## PHASE 1 — user-facing catalog

### T1 — Schema foundation `[backend]` — deps: none
**Owns:** `backend/models.py`, `backend/migrations/versions/<rev>_system_recipe_catalog.py`, `backend/migrations/README.md`, `backend/schemas.py`, `backend/recipe_copy.py`, `backend/auth_users.py`, `backend/ratelimit.py`, `backend/catalog.py` (skeleton + T1 symbols only), `backend/tests/conftest.py`, and new tests `tests/test_catalog_schema.py`, `tests/test_admin_flag_unwritable.py`. Existing tests may be edited only for the `_duplicate` → `duplicate` rename.

**Tests first:**
- Schema tests:
  - `is_system` and `is_admin` default false
  - a second `is_system=True` user raises `IntegrityError` (SYS-2)
  - `catalog_entries` rejects a bad status, and rejects `retired` without `retired_at` and the reverse (DM-3/4)
  - deleting a recipe cascades to its entry
  - `Recipe.catalog_entry` is loaded
  - an index exists on `recipes.source_recipe_id`
- `'mealplanner'` is in `RESERVED_USERNAMES` (SYS-4).
- `ensure_system_account`:
  - creates the SYS-3/5/12 values (`username_changed_at` set, no password, not verified)
  - seeds tags and ingredients for that account
  - is idempotent
  - `system_user` raises `SystemAccountMissing` when the account is absent
- `from_library` is true on a recipe whose `source_user_id` is the system account and false otherwise. `RecipeOut` then masks `source_author_username` (D7), and `GET /recipes` shows it.
- `duplicate` is public. It copies `bulk_prep` for the adoption-like direct call **and** through `copy_recipe` (D2). The existing `copy_recipe` side-copy tests (CP-6) stay green.
- `require_admin`: 401 unauthenticated, 403 non-admin, returns the user for an admin. Test it on a throwaway route mounted in the test.
- `GET /auth/me` includes `is_admin`.
- PRV-4 (TST-6): send `"is_admin": true` in the body of every user-updating endpoint:
  - `POST /auth/register`
  - `POST /auth/google` (mock verification as the existing tests do)
  - `POST /auth/verify-email`
  - `POST /auth/reset-password`
  - `PUT /auth/me/default-people`
  - `PUT /auth/me/unit-system`
  - `PUT /plan/settings` (read-only use of the existing route, API-19)
  - `POST /auth/username`

  Assert that no user's `is_admin` became true.

**Implement:**
- `User.is_system` and `User.is_admin`: `Boolean, nullable=False, default=False, server_default=false()`. Add `Index("uq_user_single_system", is_system, unique=True, postgresql_where=is_system)` to `__table_args__`.
- `CatalogEntry` model, exactly per DM-1..4, with both named `CheckConstraint`s and `recipe = relationship("Recipe", back_populates="catalog_entry")`. First check whether `Base.metadata` has a naming convention that would rename the constraints.
- `Recipe.source_recipe_id` gets `index=True`, and `Recipe.catalog_entry = relationship(..., uselist=False, passive_deletes=True)`.
- `Recipe.from_library = column_property(func.coalesce(select(User.is_system).where(User.id == source_user_id).correlate_except(User).scalar_subquery(), false()))`. This is not a DB column, so DM-7 and the migrations are unaffected. Declare it after `source_user_id`.
- Migration setup:
  ```powershell
  docker exec mp_test_pg psql -U user -d postgres -c "CREATE DATABASE mealsdb_alembic_t1;"
  $env:DATABASE_URL='postgresql://user:pass@localhost:5432/mealsdb_alembic_t1'; $env:JWT_SECRET='x'
  alembic upgrade head
  alembic revision --autogenerate -m "system recipe catalog"
  ```
  All in one command.
- Then hand-correct the script (MIG-1..8):
  - `down_revision='a1d4f7b2c903'`
  - named CHECKs, `server_default=sa.false()`
  - the partial unique index with `postgresql_where=sa.text('is_system')`
  - `ix_recipes_source_recipe_id`
  - a full `downgrade()`
  - no data
- Add an "Alembic revisions" changelog section to `migrations/README.md` containing this revision (MIG-10).
- `schemas.UserOut.is_admin`. `RecipeOut.from_library`, plus a `model_validator(mode="after")` that nulls `source_author_username` when `from_library` is true. Do not touch the visibility validator (P2-3).
- `recipe_copy`: rename `_duplicate` → `duplicate`, add it to `__all__`, add `bulk_prep=source.bulk_prep`, and keep `copy_recipe` using it.
- `auth_users.require_admin(current_user=Depends(get_current_user))` → 403 `"Forbidden"`.
- `ratelimit.CATALOG_ADOPT_RATE_LIMIT` (env, default `"30/hour"`) and `CATALOG_ADMIN_RATE_LIMIT` (default `"120/hour"`).
- `catalog.py`: a module docstring stating CAT-1/CAT-11, plus the T1 symbols from Contracts.
- `conftest.py` fixtures:
  - `system_account(db_session)`: calls `catalog.ensure_system_account`, then `db_session.execute(delete(models.CatalogEntry))` so each test starts with an empty catalog inside its rolled-back transaction.
  - `make_catalog_recipe(title, course="main", status="published", ingredients=(("Pasta", 80, "g"),), tags=("pasta",), procedure="Cook it.", bulk_prep=False, servings=1)`: inserts a system-owned `Recipe` and a `CatalogEntry` directly, resolving names in the system namespace.
  - `admin_user(db_session)`: a user with `is_admin=True` set directly, which is test-only.

**Verify:** the backend suite **including** `tests/test_migrations.py` on `mealsdb_test_t1`, then `python -m flake8 .`. A fresh `docker compose` seed must still succeed (the new columns have defaults).

### T2 — Port the pack to JSON `[data]` — deps: none
**Owns:** `backend/data/catalog_pack.json` and `backend/tests/test_catalog_pack.py`. A throwaway conversion script lives in the agent's scratchpad and is **not committed**.

**Tests first (TST-3):**
- the file is a JSON array of 60 entries: 26 main, 20 side, 14 first-course (INIT-2)
- titles are unique
- every ingredient `name` exactly matches a name in `system_ingredients.json` (INIT-5; exact case, because `get_or_create_ingredient` resolves by name)
- every tag is in `system_tags.json` (INIT-6)
- keys are exactly the INIT-3 set, with no `minutes`, `blurb` or `slug` (INIT-4)
- `servings` is an int ≥ 1
- `unit` ∈ g/ml/piece and `quantity` > 0
- `piece` quantities are integers
- `procedure` is non-empty and every recipe has ≥ 1 ingredient, so CAT-10 will accept it
- `bulk_prep` is a bool

**Implement:**
- Write a Node ESM script that imports `STARTER_RECIPES` from `frontend-v2/src/constants/starterRecipes.js` and emits the array with `servings: r.servings ?? 1`. Quantities are copied verbatim (INIT-7).
- Map any case mismatch to the canonical system spelling, and list every mapping in the report.
- The output is 2-space indented, with one recipe per block for readable diffs.

**Verify:** `python -m pytest tests/test_catalog_pack.py` (it needs no DB fixture, but conftest still needs `TEST_DATABASE_URL` set to the agent's DB), then flake8.

### T3 — Discover page (user-facing) `[frontend]` — deps: none (builds against Contracts with mocked API)
**Owns:**
- New files: `src/api/catalogApi.js` + `src/api/__tests__/catalogApi.test.js`, `src/pages/DiscoverPage.jsx`, `src/pages/__tests__/DiscoverPage.test.jsx`, `src/components/CatalogRecipeCard.jsx`
- Edited files: `src/components/RecipeSort.jsx` (+ its test), `src/components/index.js`, `src/App.jsx`, `src/__tests__/App.test.jsx`, `src/components/Sidebar.jsx`

**Must not touch:** `RecipesPage.jsx` or `AttributionLine.jsx` (T4).

**Tests first (TST-8):**
- `catalogApi.list` builds repeatable `course` and `tags` params and encodes `q`. `adopt` POSTs `{recipe_ids}`.
- `DiscoverPage` renders cards from a mocked list:
  - each card shows the adoption count as a number only (UI-13)
  - the default sort is "Most added" and changing it calls `list` with `sort=title`
  - course and tag filters and debounced search call `list` with those params
  - `ActiveFilterChips` removes a filter
- Opening a card shows its ingredients and procedure from `catalogApi.get` (UI-7).
- Selection:
  - selecting two cards shows "Add 2 recipes"
  - an `in_my_book` card shows "In your book" and has no checkbox (UI-8/9)
- Adding:
  - success calls `adopt([ids])`, shows a `role="status"` message, refetches, and clears the selection
  - failure shows `role="alert"` naming the failure and **keeps the selection** (UI-15)
- The empty state and the error state each render text rather than a blank page (UI-14).
- No admin controls render, even for `is_admin: true`. They are added in T10.
- `App.test`: `/discover` renders DiscoverPage and joins the unconfirmed-handle path list. The Sidebar shows "Discover" directly after "Recipes".
- `RecipeSort` accepts an `options` prop (default: the existing `SORT_OPTIONS`) and a `showDirection` prop (default true).

**Implement:**
- **Reuse** `RecipeFilters`, `RecipeSort` and `ActiveFilterChips` (UI-5), plus `Card`, `Badge`, `Button`, `Modal`, `BottomSheet` (mobile filters, as in `RecipesPage.jsx:776-794`), `Quantity`, `.card-grid`, and the course icons and colours from `constants/recipeIcons.js`.
- Course options come from `COURSES` in `constants/recipeImport.js`. Tag options come from `tagsApi.fetchAll()` filtered to `is_system`.
- Filtering, search and sort are **server-side** through the query params.
- Borrow the multi-select checkbox pattern from `StarterRecipesModal.jsx:35-51`; copy the pattern, do not import the file, because T4 deletes it.
- The sticky action bar has 44 px tap targets.
- Routing and navigation:
  - add the `/discover` route before the catch-all in `App.jsx`
  - add a `NAV` entry `{label:'Discover', path:'/discover', Icon: SparklesIcon, color: <an unused category token from the design guide>}` after Recipes
  - `NavDrawer` reuses `Sidebar`, so it needs no change
- Follow `MEAL_PLANNER_DESIGN_GUIDE.md` §6 and §8.

**Verify:** `npm run test` and `npm run lint`.

### T4 — Starter-pack removal + library attribution `[frontend]` — deps: none
**Owns:**
- `src/pages/RecipesPage.jsx` + `src/pages/__tests__/RecipesPage.test.jsx`
- `src/components/AttributionLine.jsx` + its test
- `src/api/recipesApi.js` + its test
- `src/tutorial/PageTour.jsx` (comment only)
- a new `src/__tests__/noStarterPack.test.js`
- deletions: `constants/starterRecipes.js`, `components/StarterRecipesModal.jsx`, `constants/__tests__/starterRecipes.test.js`, `components/__tests__/StarterRecipesModal.test.jsx` (RM-1..3)

**Tests first:**
- `AttributionLine`:
  - `from_library: true` renders exactly "From the recipe library" and never the handle, even when `source_author_username` is present (UI-10)
  - the existing `@handle` tests still pass (FC-4, TST-9)
- `recipesApi.normaliseRecipe` passes `from_library` through.
- `RecipesPage`:
  - an empty book shows a call to action that navigates to `/discover` (RM-6; wrap renders in `MemoryRouter`)
  - there is no starter modal and no `sessionStorage` use
  - the filtered-empty message still appears only when `recipes.length > 0`
  - `PageTour` is enabled once loaded on an empty account (RM-5)
- The three starter tests at `RecipesPage.test.jsx:399-433` are replaced by the CTA tests.
- `noStarterPack.test.js` walks `frontend-v2/src` and asserts no file contains `'starter' + 'Recipes'` or `'StarterRecipes' + 'Modal'` (RM-8). Build the strings by concatenation so the test does not match itself.

**Implement:**
- Remove every item in RM-4:
  - `RecipesPage.jsx:111-116` (lazy import and key)
  - `:126-130` (`showStarter`)
  - `:170-172` (trigger)
  - `:720-734` (modal)
  - the `ingredientRows` comment and state at `:147-150`, if only the names remain used
- RM-5: `enabled={loaded}`.
- RM-7: rewrite the comment at `:538` to cite RM-6.
- The empty state is a `Card` with a short line and a primary `Button` "Browse the recipe library" → `useNavigate()('/discover')`.
- Drop the starter comment at `PageTour.jsx:14-16`.

**Verify:** `npm run test` and `npm run lint`.

### T5 — Catalog service `[backend]` — deps: T1
**Owns:** `backend/catalog.py` (adds the T5 symbols) and `backend/tests/test_catalog_service.py`.

**Tests first (TST-1, TST-2, §13):**
- Publish and retire:
  - `publish` creates an entry; repeating it keeps `published_at` (CAT-6)
  - `retire` sets status and `retired_at` and keeps the recipe row (CAT-8)
  - re-publishing clears `retired_at` and keeps the original `published_at` (CAT-7, FC-8)
  - `publish` on a user-owned recipe raises `PermissionError` (CAT-9)
  - a missing title, ingredients or procedure raises `IncompleteRecipe` naming the part (CAT-10)
- Listing:
  - `list_published` hides retired entries (CAT-4/RET-1)
  - course filter, AND tag filter, and a case-insensitive `q`; `q="50%"` and `q="a_b"` match literally (ERR-11)
  - `popular` order with the title tie-break, and `title` order (POP-7)
  - ingredient and tag access issues no extra queries; assert with a SQLAlchemy `before_cursor_execute` counter (CAT-5)
- Counts:
  - `adoption_counts` is one query
  - it counts distinct users, so two copies by one user count once
  - it excludes the system account (POP-3)
  - it drops after a user deletes their copy (ERR-10)
  - a retired entry keeps its count (RET-4)
- `held_by` reports correctly for two users (API-3).
- Adoption:
  - creates copies with the full snapshot, `private`, `copy_count=0`, no score or dates (ADO-8/9/10), and `bulk_prep` preserved (D2)
  - ingredients and tags land in the adopter's namespace, so an adopter-owned "Pasta" is reused (ADO-11/12)
  - a catalog main **with favourite sides** creates exactly one recipe (ADO-2/TST-2), cross-referencing the existing `copy_recipe` sides test
  - an already-held recipe is skipped (ADO-7); all-held creates nothing (ERR-4)
  - the same batch twice gives no duplicates (ERR-12); duplicate ids in one batch count once
  - an unpublished, retired or foreign id raises `CatalogEntryNotFound` with nothing written (ADO-14/6)
  - a monkeypatched failure on the 2nd duplicate rolls back the 1st (ADO-6)
  - exactly one commit (spy on `session.commit`, ADO-5)
  - an empty list or `ADOPT_BATCH_MAX+1` raises `ValueError` (ERR-2/3)
  - source `copy_count` increments (ADO-16)
- The export and admin functions are **not** part of T5.

**Implement:** follow the Contracts table. Timestamps use `datetime.utcnow()`, as `recipe_copy` does.

**Verify:** the backend suite (minus migrations) on `mealsdb_test_t5`, then flake8.

### T6 — Seed scripts `[backend]` — deps: T1
**Owns:** `backend/scripts/seed_testing_data.py`, `backend/scripts/seed_user_data.py` (review; change only if needed per SEED-8), and a new `backend/tests/test_seed_catalog_data.py`, modelled on `tests/test_seed_sharing_data.py`.

**Tests first:** after running `populate(session)`:
- exactly one `is_system` user, with the SYS-3/5 values (SEED-1)
- it owns tags and ingredients (SEED-2)
- ≥ 6 system-owned catalog recipes with published entries (SEED-3), and ≥ 1 retired entry (SEED-4)
- adoptions by demo users produce **at least three distinct** adoption counts (SEED-5), checked with a grouped count query rather than `catalog.py`, which does not exist in this branch yet
- exactly one `is_admin` user, `demo@mealplanner.test` (SEED-6)
- the script still refuses to run without `ALLOW_DESTRUCTIVE_SEED` (SEED-7)

**Implement:**
- In `populate()`, after the accounts are created, call `catalog.ensure_system_account(session)`.
- Choose ≈ 10 entries from the in-file `RECIPES` whose ingredients exist in the system namespace. Resolve any missing ingredient in the system namespace using the seed's `INGREDIENTS` metadata. Create them owned by the system account with `procedure` text and a `CatalogEntry` each, with one of them `retired` + `retired_at`.
- Create adoptions with `recipe_copy.duplicate(session, source, demo_user)` for demo_chef, friend_cook and guest_cook, with varied overlap (e.g. entry A adopted by 3 users, B by 2, C by 1).
- Set `demo_user.is_admin = True` with a comment: `# SEED-6: demo_chef (demo@mealplanner.test / demo1234) is the only admin`.
- Keep the single final commit.

**Verify:** the backend suite (minus migrations) on `mealsdb_test_t6`, flake8, and a manual run: `$env:DATABASE_URL=<own db>; $env:ALLOW_DESTRUCTIVE_SEED='1'; $env:JWT_SECRET='x'; python scripts/seed_testing_data.py`.

### T7 — User-facing catalog routes `[backend]` — deps: T5
**Owns:** `backend/catalog_routes.py`, `backend/main.py` (**only** the `import catalog_routes` line and the `include_router` line after `ops_routes`), `backend/tests/test_app_wiring.py`, and new `tests/test_catalog_routes.py` and `tests/test_catalog_isolation.py`.

**Must not touch:** `catalog.py`. Report any service gap instead.

**Tests first:**
- Listing:
  - exact row keys per Contracts; no `procedure`, `score`, `date_last_*`, `copy_count`, `visibility`, `user_id`, `email` or `username` (API-2/4/8)
  - the serialised body never contains `"mealplanner"` (API-7/PRV-3)
  - repeatable `course` and `tags` params work, as do `q` and `sort` (API-1)
  - `in_my_book` flips after adopting (API-3)
- Detail: includes `procedure`; 404 for retired, uncatalogued and another user's recipe (API-5).
- Adopt:
  - returns `created_ids` and `skipped_ids`
  - 400 for empty and for over-limit, with the limit named in `detail`
  - 404 for a non-published id, with nothing created
  - repeating the same batch gives all skipped (ERR-1..4, ERR-12)
  - adopting another user's recipe id, or a user copy of a catalog recipe, returns 404 (PRV-6)
  - with `app.state.share_limiter.enabled` monkeypatched to True, the per-user limit returns 429 (ADO-13)
- All three routes return 401 for anonymous callers (P2-4).
- With the system account removed inside the transaction, `GET /catalog/recipes` returns 500 and the log names the missing account (ERR-5, `caplog`).
- The adopter's `GET /recipes` shows the copy with `from_library: true` and a null `source_author_username`, and shows no system recipes (API-16/17).
- `visibility="public"` is still rejected on `POST /recipes`, and every catalog recipe is `private` (TST-5/P2-3).
- **TST-7 isolation:** user A adopts; user B's listing shows `in_my_book=false` and the incremented count, and B cannot see A's copy through any catalog or recipe route.
- `test_app_wiring`: `catalog_routes.router` is included (TST-10).
- Existing sweeps pass unchanged: `test_forward_compat.py`, `test_private_unreachable.py`, `test_provisional_handle_exposure.py`.

**Implement:**
- `router = APIRouter(prefix="/catalog", tags=["catalog"])` with local Pydantic models and local `Db`/`CurrentUser` aliases, following `share_routes.py:38-41`.
- `AdoptIn.recipe_ids: list[int]` has no `min_length`; the service's `ValueError` maps to 400.
- Adopt carries `@ratelimit.limiter.limit(ratelimit.CATALOG_ADOPT_RATE_LIMIT)` with `request: Request` as the first parameter.
- Rows are built from `CatalogRow` + `held_by` + `adoption_counts`: one query each for the whole listing.

**Verify:** the backend suite (minus migrations) on `mealsdb_test_t7`, then flake8.

### T8 — Bootstrap population from the pack `[backend]` — deps: T2, T5
**Owns:** `backend/catalog.py` (adds `populate_from_pack` + `PACK_PATH`), `backend/main.py` (**only** inside `_bootstrap`), `backend/tests/test_architecture_guards.py`, and new `tests/test_catalog_bootstrap.py`. It may also fix existing tests broken by import-time population, but only by scoping their assertions, never by weakening them; each such fix is listed in the report.

**Tests first:**
- On an empty catalog, `populate_from_pack` creates the system account if absent, 60 published entries, and recipes whose ingredients bind to the system account's seeded rows (with seasonality intact) (INIT-9).
- Running `main._bootstrap(db_session)` twice leaves 60 entries (INIT-10/13, TST-4).
- An edited catalog recipe title survives a second bootstrap (INIT-11, TST-4).
- One retired entry and zero published ones means the pack is not re-applied (INIT-10).
- A pack file carrying `status: "retired"`, `published_at` and `retired_at` loads with all entries `published` (EXP-5).
- Every loaded recipe is `private` (P2-3).
- `test_architecture_guards`: `catalog.py` imports none of `main`, `*_routes`, `public_pages`, `ops_routes` or `frontend-v2` (CAT-11/TST-11). Parse the imports with `ast`.

**Implement:**
- `populate_from_pack`:
  1. `ensure_system_account`
  2. return 0 if any `CatalogEntry` joined to a system-owned recipe exists
  3. for each item, create a `Recipe(user_id=system.id, …)`, with ingredients resolved by `crud.get_or_create_ingredient(session, None, name, system.id)` and tags by `crud.get_or_create_tag`, plus `CatalogEntry(status="published")`
  4. ignore extra keys
  5. a single commit
- Call it in `_bootstrap` before the final commit, with a comment citing INIT-8.
- Run the **full** suite: import-time population now puts 60 recipes into the test DB, so fix any fallout by scoping assertions.

**Verify:** the backend suite (minus migrations) on `mealsdb_test_t8`, then flake8.

### I1 — Integration → **PAUSE 1** (orchestrator)
**Gate:**
- all of T1–T8 merged
- `docker start mp_test_pg`; `python -m pytest` (full suite, including migrations) and `python -m flake8 .` from `backend/`
- `npm run test` and `npm run lint` from `frontend-v2/`
- `docker compose down -v; docker compose up --build`, then `curl` confirms `GET /catalog/recipes` returns data with a valid token
- the T3 mocked contract matches the real responses: log in through the UI and load `/discover`

**User checklist (present verbatim):**
1. `docker compose up --build`, then open http://localhost:3000.
2. Log in as `friend@mealplanner.test` / `demo1234`. The sidebar shows **Discover** right after Recipes, on desktop and in the mobile drawer.
3. Discover lists the seeded catalog, sorted by most added, with varied counts. The retired seed entry is absent.
4. Filter by course and by two tags, and check that the chips remove them. Search for part of a title, and search for `%`, which should match nothing unexpectedly. Switch the sort to title.
5. Open a recipe and confirm the ingredients and procedure are shown.
6. Select 2–3 recipes and check the button reads "Add N recipes". Add them, and confirm the success message and that the cards now show "In your book" and are not selectable.
7. Go to Recipes. The adopted copies show "From the recipe library", no @handle anywhere, and their bulk-prep flag is preserved.
8. Delete one adopted copy, then return to Discover. Its count has dropped by one and it can be added again.
9. Register a new account (the verification link is in the `backend` container log). The empty Recipes page shows the "Browse the recipe library" button, which goes to Discover. The starter modal never appears, and the page tour still runs.
10. As `demo@mealplanner.test`, check that no admin controls are visible yet (they arrive in Phase 2).

**Wait for the user's go-ahead before Phase 2.**

---

## PHASE 2 — admin curation

### T9 — Admin service + routes `[backend]` — deps: I1
**Owns:** `backend/catalog.py` (adds the T9 symbols), `backend/catalog_admin_routes.py`, `backend/main.py` (the import and `include_router` lines only), `backend/tests/test_app_wiring.py`, and new `tests/test_catalog_admin.py` and `tests/test_catalog_export.py`.

**Tests first:**
- Every `/admin/catalog/*` route and method returns 401 for anonymous callers and 403 for a non-admin. The 403 body is identical for an existing and a non-existent `recipe_id` (API-15, ERR-8, PRV-5).
- `POST /recipes` creates a **system-owned** recipe with a published entry. With `publish: false` it creates no entry. Neither the admin's own pantry nor the admin's tag rows change: count them before and after (ADM-7, ADM-12).
- An unknown ingredient or tag name gives 400 (D3). CAT-10 incompleteness gives 400 naming the part (ERR-6).
- `PUT` updates the recipe, replacing ingredients and tags. An adopter's existing copy is unchanged (non-objective: no re-sync). A `PUT` on a user-owned recipe gives 404.
- `publish` on another user's recipe gives 403 (ERR-7/ADM-8). `publish` and `retire` follow CAT-6/7/8 over HTTP, and the retired entry vanishes from `GET /catalog/recipes` **for the admin too** (RET-1).
- `GET /recipes` (admin) lists published and retired entries with `status` and `adoption_count` (API-9).
- `GET /ingredients` and `GET /tags` return the system account's rows only.
- Export (EXP-1..4):
  - it contains both statuses and the exact keys
  - its body contains no `adoption_count`, email, handle, `user_id` or `"mealplanner"`
  - a round trip (export → temp file → `populate_from_pack` on an emptied catalog) recreates every entry as `published` (EXP-5)
- No DELETE route exists under `/admin/catalog` (API-14, route-table assertion).
- The admin's own `GET /recipes` does not include system recipes (ADM-9/10).
- Write routes return 429 once the limiter is enabled (ADM-11).
- `test_app_wiring` includes `catalog_admin_routes.router`.

**Implement:**
- Service functions:
  - `create_catalog_recipe(session, data, *, publish=True)` and `update_catalog_recipe(session, recipe_id, data)`: resolve names against the system account's existing ingredients and tags only, raising `ValueError("Unknown ingredient: X")`; the routes commit.
  - `list_all(session)`
  - `export_catalog(session)`, ordered by title
  - `system_ingredients` and `system_tags`
- Router with `prefix="/admin/catalog"` and `dependencies=[Depends(auth_users.require_admin)]`. Write routes use `@ratelimit.limiter.limit(ratelimit.CATALOG_ADMIN_RATE_LIMIT)`. Local Pydantic models. Nothing writes `is_admin` (ADM-2).

**Verify:** the backend suite (minus migrations) on `mealsdb_test_t9`, then flake8.

### T10 — Admin UI on /discover `[frontend]` — deps: I1 (built against Contracts with mocks)
**Owns:** `src/api/catalogApi.js` (+ its test), `src/pages/DiscoverPage.jsx` (+ its test), `src/components/NewRecipeModal.jsx` (+ its test if present), and new admin sub-components under `src/components/catalog/` if they keep `DiscoverPage` readable.

**Tests first (TST-8 admin part):**
- A user with `useAuth().user.is_admin` falsy sees no admin toolbar, edit, publish, retire, retired toggle or export control (UI-11).
- For an admin:
  - "New catalog recipe" opens `NewRecipeModal` in catalog mode, which loads `catalogApi.admin.ingredients` and `catalogApi.admin.tags` (not `ingredientsApi`) and hides "add new ingredient"
  - saving calls `admin.create` and then refetches
  - Edit from the detail view calls `admin.update`
  - the "Show retired" toggle issues a **separate** `admin.list` request and renders a status badge with Publish or Retire per row (UI-16)
  - Retire and Publish call their endpoints and refresh
  - Export calls `admin.exportCatalog` and triggers a download through a Blob URL
  - an admin API error shows `role="alert"` (the modal closes before `onSave` resolves, so the page owns error feedback)
- `NewRecipeModal`:
  - defaults are unchanged; the existing `RecipesPage` tests stay green
  - with `loadIngredients`/`loadTags` props it uses those
  - with `allowCreateIngredient={false}` there is no add-ingredient button
  - check how `recipesApi.uploadImage` is scoped; if it needs a user-owned recipe, `allowImageUpload={false}` hides upload in catalog mode

**Implement:**
- Add optional props to `NewRecipeModal`: `loadIngredients`, `loadTags`, `allowCreateIngredient = true`, `allowImageUpload = true`, and `heading`.
- The admin payload serialiser in `catalogApi.admin` maps `hot` → `bulk_prep` and `amount` → `quantity`, and sends names only.
- Read `is_admin` with `useOptionalAuth()`.
- Follow the design guide: the ghost/secondary button hierarchy, and `Badge` tones for status.

**Verify:** `npm run test` and `npm run lint`.

### I2 — Integration → **PAUSE 2** (orchestrator)
**Gate:** the same as I1 plus T9 and T10 merged, and a compose rebuild.

**User checklist:**
1. `docker compose down -v; docker compose up --build`.
2. Log in as `demo@mealplanner.test` / `demo1234` (the admin). Discover shows the admin controls.
3. Create a catalog recipe. The ingredient picker shows library ingredients and has no "add ingredient" option. The recipe appears in Discover, and your own Ingredients page is unchanged.
4. Edit its title and check that Discover updates.
5. Log in as `friend@mealplanner.test`, add that recipe, and confirm the friend sees no admin controls. Log back in as admin and edit the recipe again. The friend's copy keeps the old title.
6. Retire the recipe. It disappears from Discover, including for the admin. **Show retired** lists it, and **Publish** restores it with the same count.
7. **Export** downloads JSON that includes the retired entries and contains no emails, handles or counts.
8. Optional: calling `/admin/catalog/recipes` with the friend's token returns 403.

**Wait for the user's go-ahead before Phase 3.**

---

## PHASE 3 — finish

### T11 — Definition-of-done sweep + /simplify (orchestrator, or one agent in the main checkout; sequential)
1. Remove the stale "starter pack" comments at `backend/mealplanner/seed.py:38` and `backend/tests/test_seed.py:194`. Repository-wide, `git grep -n "starterRecipes\|StarterRecipesModal" -- ':!docs'` must be empty. Historical docs and specs are left as a record, and the report says so explicitly.
2. Update the `CLAUDE.md` Architecture section:
   - add `catalog_routes.py` and `catalog_admin_routes.py` to the router list
   - add `catalog.py` to the backend layers
   - add `DiscoverPage` to `pages/`
   - note that `is_admin` is granted by SQL only
3. Fresh-DB bootstrap check. It should print `60`:
   ```powershell
   docker exec mp_test_pg psql -U user -d postgres -c "CREATE DATABASE mealsdb_fresh;"
   $env:DATABASE_URL='postgresql://user:pass@localhost:5432/mealsdb_fresh'; $env:JWT_SECRET='x'; alembic upgrade head; python -c "import main, models; from database import SessionLocal; from sqlalchemy import select, func; s=SessionLocal(); print(s.scalar(select(func.count()).select_from(models.CatalogEntry).where(models.CatalogEntry.status=='published')))"
   ```
4. Pre-deploy note for the user: no existing production user may already hold the handle `mealplanner` (`SELECT id FROM users WHERE lower(username)='mealplanner'`), or startup `ensure_system_account` fails loudly.
5. Run the **`/simplify` skill** over the branch diff (`git diff main...HEAD`) and apply its fixes. Likely candidates:
   - duplicated card media between `RecipesPage` and `CatalogRecipeCard`
   - duplicated row builders between the two routers
6. Re-run everything: `python -m pytest` (full), `python -m flake8 .`, `npm run test`, `npm run lint`, and `docker compose down -v; docker compose up --build`.

### **PAUSE 3 — final review**
Report the spec §21 DoD checklist item by item, with evidence (command output). Include:
- the written deviations: D2 (share copies now keep `bulk_prep`), D3 (two extra admin read routes and name rejection), and the D7 JSON-LD residual
- any test scoped in T8

Then offer the user the next step: a PR, or further changes.

---

## Critical files (quick reference)
- **Backend:** `backend/models.py`, `backend/schemas.py`, `backend/recipe_copy.py`, `backend/auth_users.py`, `backend/ratelimit.py`, `backend/main.py` (`_bootstrap` at :50-71, routers at :97-100), new `backend/catalog.py`, `backend/catalog_routes.py`, `backend/catalog_admin_routes.py`, `backend/data/catalog_pack.json`, `backend/scripts/seed_testing_data.py`, `backend/tests/conftest.py`.
- **Frontend:** `src/App.jsx`, `src/components/Sidebar.jsx`, `src/components/RecipeSort.jsx`, `src/components/AttributionLine.jsx`, `src/components/NewRecipeModal.jsx`, `src/pages/RecipesPage.jsx`, new `src/pages/DiscoverPage.jsx`, `src/api/catalogApi.js`.
- **Reused as-is:**
  - `recipe_copy.existing_copy`
  - `crud.get_or_create_ingredient` / `get_or_create_tag` / `create_user`
  - `mealplanner.seed.seed_system_tags` / `seed_system_ingredients`
  - `ratelimit.limiter`
  - `usernames.seed_reserved`
  - `RecipeFilters`, `ActiveFilterChips`, `Modal`, `BottomSheet`, `Quantity`, `api/client.request`
  - the `conftest` helpers `client_as` / `db_client`
- **Never modified:** `shares.py`, `share_routes.py`, `public_pages.py`, `public_schema.py`, `public_markup.py`, `public_copy.py`, `mealplanner/planner.py`, `mealplanner/scoring.py`, any `/plan` route.
