# System Recipe Catalog ("Discover") — Implementation Report

**Branch:** `feature/system-recipe-catalog` (not merged to `main`; no PR opened)
**Spec:** [`../specs/2026-09-12-system-recipe-catalog-design.md`](../specs/2026-09-12-system-recipe-catalog-design.md)
**Plan:** [`2026-09-13-system-recipe-catalog.md`](2026-09-13-system-recipe-catalog.md)
**Implemented:** 2026-09-13 → 2026-09-16, as 11 tasks (T1–T11) in parallel git worktrees, reviewed and merged one at a time.

This file records what the spec and plan do **not** say: the decisions taken while implementing,
the deviations, the residual risks, and the follow-ups. The requirement IDs it cites are the spec's.

---

## 1. Definition of done (spec §21) — final state

| Item | Evidence |
|---|---|
| `pytest` from `backend/` | 1346 passed, including `test_migrations.py` (1073 before this work) |
| `flake8 .` from `backend/` | exit 0 |
| `npm run test` / `npm run lint` | 935 passed (832 before) / clean |
| Migration drift | none; revision `67f3715acf44`, `down_revision='a1d4f7b2c903'`, full `downgrade()` |
| Seed script | 10 catalog entries, 1 retired, adoption counts 3/2/1, `demo_chef` the only admin |
| `docker compose up` on a fresh volume | healthy; listing, adopt, admin listing, export and non-admin 403 verified live |
| Fresh DB via `_bootstrap` alone | 60 published entries, still 60 after a second start; all 377 ingredient lines bind to system-owned ingredients |
| Starter pack gone | `git grep -n "starterRecipes\|StarterRecipesModal" -- ':!docs'` is empty (`docs/` keeps the history on purpose) |
| `/simplify` run last | 4 review agents → 2 fix agents; see §5 |

Manual acceptance testing was done by the user at Pause 1 (user-facing) and Pause 2 (admin curation).

---

## 2. Deviations from the spec, with justification

| # | Deviation | Why |
|---|---|---|
| D2 | `recipe_copy.duplicate` copies `bulk_prep`, so **user-to-user share copies keep it too** | Whether a dish keeps as leftovers is a fact about the recipe, not planner history (CP-7 is unaffected). Both paths are tested. |
| D3 | Two admin read routes beyond spec §10.2: `GET /admin/catalog/ingredients` and `/tags` | The admin form reuses `NewRecipeModal` and must offer the **system account's** vocabulary (ADM-12). Unknown names are rejected with 400; no ingredient or tag is ever created from the catalog form. |
| D7 | Adopted copies keep `source_author_username='mealplanner'` (ADO-8's full snapshot), masked on output by `RecipeOut` | See the residual in §4. |

---

## 3. Decisions taken during implementation

### 3.1 Taken by the user, when the plan did not cover the case

1. **Import-time catalog vs. the test suite.** Importing `main` runs `_bootstrap`, which loads 60 system
   recipes into the test database; 46 existing low-level tests (planner, import/export, ingredients) run
   *unscoped* (`user_id=None`) and saw them. The suite passed only by test-ordering luck.
   **Chosen:** one session-scoped cleanup in `tests/conftest.py` (`_without_import_time_catalog`) that removes
   what the import-time bootstrap created, **plus** a new guard in `tests/test_architecture_guards.py`
   asserting that every *production* call to a `crud`/`planner` function taking `user_id` passes it.
   Rejected: per-test hiding (slower), and rewriting the 46 tests (churn, and it would have dropped coverage
   of the deliberately unscoped paths).
2. **Startup race.** Two instances starting at once on an empty catalog could both load the pack (120 entries).
   **Chosen:** a transaction-scoped Postgres advisory lock (`POPULATE_LOCK_KEY`) taken after
   `ensure_system_account` and before the emptiness check.
3. **Seeded demo accounts cannot log in** (see §4) — **out of scope** for this branch, to be fixed separately.

### 3.2 Taken by the orchestrator (engineering calls inside the plan's intent)

- **`ensure_system_account` does not use `crud.create_user`.** That helper commits before `is_system` could be
  set, so a crash or a concurrent start could leave a committed `mealplanner` user *without* the flag; SYS-6
  forbids finding it by handle, so every later start would fail recreating the handle — an unrecoverable boot
  loop. The row is now built directly and only ever flushed **carrying** the flag (SYS-3/5/10/12 unchanged).
- **`RecipesPage`'s empty-book CTA requires a *successful* empty load.** After a failed load the page no longer
  claims the book is empty (the old starter offer had the same semantics).
- **Discover locks the selection while an add is in flight**, so recipes ticked mid-request cannot be silently
  discarded by the success handler (UI-8/UI-15).
- **The admin form does not offer to create tags** (`allowCreateTag={false}`), matching D3's "no new ingredients"
  intent; the server rejects unknown tags anyway.
- **Admin validation errors are readable.** FastAPI 422 bodies carry a `detail` *array*, which `api/client.js`
  surfaces as raw JSON; the admin UI validates ingredient amounts/units before sending and formats any
  remaining 422 into a sentence.

### 3.3 Taken by implementing agents and accepted on review

- **Drafts:** `POST /admin/catalog/recipes` with `publish:false` creates a system-owned recipe with no entry.
  It is not listed (`GET /recipes` lists entries) and is reachable only by the id in the 201 body; `PUT` and
  `publish` accept it. The admin UI always publishes on create, so no draft is reachable from the UI.
- **Editing a published recipe into an incomplete state is rejected** with 400 naming the missing part
  (CAT-10 re-checked on update); retired entries and drafts may be left incomplete.
- **Name matching is exact and case-sensitive**, as `crud.get_or_create_*` already is. A repeated ingredient
  name gives 400 `Duplicate ingredient: X` rather than a primary-key 500.
- **Image upload stays enabled in the admin form**: `POST /recipes/upload-image` is plain storage, not tied to a
  recipe or owner.
- **ERR-5 (no `is_system` account)** is a per-route `except` in `catalog_routes.py` and a router-level
  dependency in `catalog_admin_routes.py`. Two mechanisms, because `catalog.retire` never looks the account up;
  unifying them would change edge-case status codes.
- **Seed data:** `demo_chef` adopts "Spaghetti Pomodoro", which it already owns, so it holds two recipes of that
  title. Three distinct adoption counts need all three demo users. Nothing looks that title up ambiguously.

---

## 4. Residual risks and known issues

1. **D7 / JSON-LD leak (accepted).** An adopted copy that the user then shares by link renders
   `source_author_username` — the system handle — in that share page's JSON-LD (`public_schema.py:80`), which
   P2-5 forbids this work from touching. The API itself never exposes the handle.
2. **Seeded demo accounts cannot log in (pre-existing, `main` too).** `email-validator` 2.3.0 (pulled unpinned
   via `pydantic[email]`) rejects the reserved `.test` domain, so `demo@/friend@/guest@mealplanner.test` get 422
   from `POST /auth/login`. Workarounds used for manual testing: register a normal address (verification link is
   in `docker compose logs backend`) and grant admin by SQL; or mint a token inside the container with
   `auth_users.create_access_token`.
3. **Single-instance assumption elsewhere.** The advisory lock covers pack loading. Two instances creating the
   *system account* simultaneously still resolve by one losing on `uq_user_single_system` and restarting.

---

## 5. `/simplify` outcome

**Applied — backend:** top-level `import catalog`; index-usable `system_user` lookup; shared
`ingredient_lines` extractor (both routers keep local models per CLAUDE.md and explicit allowlists per
API-7/8); `adopt` eager-loads sources and holds the system user (70 → 55 statements for 5 recipes);
`populate_from_pack` preloads the system vocabulary and reuses `_write` (**1145 → 254** statements per fresh
load, which also runs on every pytest session); admin publish/retire build their response before commit;
shared eager-load constants; `crud.get_recipe`/`scoping.scope` reuse; one savepoint-mode `db_session` in
conftest replacing four per-file copies; the scoping guard's line-number allowlist removed.

**Applied — frontend:** shared `RecipeMedia`, `RecipeFilterControl` + `useOnClickOutside` hook, `downloadJson`
and `toggleIn` utils; one `status` value replacing `loaded`/`loadFailed` on both pages; `CatalogRecipeDetail`
extracted; unused `allowImageUpload` prop removed; default loader props; `AttributionLine` early returns.
`DiscoverPage.jsx` 644 → 456 lines, `RecipesPage.jsx` 788 → 675.

**Skipped deliberately:**

| Finding | Why skipped |
|---|---|
| Replace per-source `existing_copy` with one `held_by`; batch `get_or_create_*` in adopt | ADO-7 and ADO-11/12 mandate those calls |
| Move the `copy_count` increment into `duplicate()` | Would change share-copy behaviour, which ADO-3 pins |
| `NewRecipeModal` should `await onSave` | Visible behaviour change; also affects `RecipesPage` and `ImportRecipeModal` — see §6 |
| Format 422 `detail` arrays inside `api/client.js` | Outside this diff; changes error text app-wide — see §6 |
| Split count query for filtered listings; memoise catalog cards; admin-view refetch tuning | Premature at 60 entries |
| Unify the two ERR-5 mechanisms | Would change edge-case status codes |

---

## 6. Follow-ups worth a separate change

1. **`NewRecipeModal` closes before the save resolves.** On `RecipesPage` a failed save silently loses what the
   user typed (the catalog form works around this by reopening itself). The deeper fix is to `await onSave` and
   keep the modal open on failure — a visible behaviour change for three callers.
2. **422 errors elsewhere still render as raw JSON** (`api/client.js` only lifts a string `detail`). Roughly 24
   `err.message` call sites would benefit.
3. **The `.test` demo-login bug** (§4.2).
4. **Pagination** past `LISTING_CAP = 500` (API-20 documents it as the next step).

---

## 7. Before deploying

- **Handle collision:** `SELECT id FROM users WHERE lower(username)='mealplanner';` must return nothing, or
  startup's `ensure_system_account` fails loudly.
- **Order of operations:** the Alembic revision creates schema only; the 60 recipes load at first startup
  (INIT-12).
- **Granting admin:** SQL only, by design (ADM-2): `UPDATE users SET is_admin = true WHERE email = '…';`
- **Alpha has no database backups** (a recorded project decision), which is why `GET /admin/catalog/export`
  exists (§9.1). Export before any risky change.
