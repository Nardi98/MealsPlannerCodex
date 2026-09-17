# Requirements — System Recipe Catalog ("Discover")

**Status**: Approved for planning.
**Date**: 2026-09-12
**Branch**: `feature/system-recipe-catalog`
**Related**: [Part 1 — User-to-User Recipe Sharing](2026-08-19-recipe-sharing-part1-user-to-user.md) (shipped;
this design builds on its machinery) and [Part 2 — Public Publishing](2026-08-19-recipe-sharing-part2-public-publishing.md)
(deferred; **this design deliberately does not begin it** — see §3).

Requirement keywords: **MUST** = mandatory. **MUST NOT** = prohibited. **SHOULD** =
strongly recommended, deviation requires written justification. **MAY** = optional.

> **For the agent writing the implementation plan**: this spec is written to be read without
> the brainstorming conversation that produced it. Every decision below was taken explicitly;
> where an obvious-looking alternative was rejected, the rationale is stated so you do not
> re-open it. §19 is a file-by-file inventory. §20 records the decisions and the alternatives
> that were rejected. CLAUDE.md's project rules apply throughout and are **not** restated
> except where this feature adds an obligation (§15, §16).

---

## 1. Context

### 1.1 What exists today

A brand-new account is seeded with **system tags and system ingredients, but no recipes**
([`backend/main.py:546-547`](../../../backend/main.py#L546-L547), calling
`mealplanner.seed.seed_system_tags` / `seed_system_ingredients`). The recipe book starts empty.

Recipes are instead proposed by a **client-side starter pack**:

| Thing | Where | Detail |
|---|---|---|
| The data | [`frontend-v2/src/constants/starterRecipes.js`](../../../frontend-v2/src/constants/starterRecipes.js) | 1416 lines, ~30 KB, 60 recipes: 26 `main`, 20 `side`, 14 `first-course`. No favourite-side pairings. |
| The UI | [`frontend-v2/src/components/StarterRecipesModal.jsx`](../../../frontend-v2/src/components/StarterRecipesModal.jsx) | 232 lines. All recipes pre-ticked; grouped by course via `groupStarterRecipes`. |
| The trigger | [`frontend-v2/src/pages/RecipesPage.jsx:170`](../../../frontend-v2/src/pages/RecipesPage.jsx#L170) | `if (recipesRes.length === 0 && sessionStorage.getItem(STARTER_DISMISSED_KEY) !== '1')`. Fires when the **book is empty**, not at registration. |
| Dismissal | [`RecipesPage.jsx:116`](../../../frontend-v2/src/pages/RecipesPage.jsx#L116) | `sessionStorage` key `starterRecipesDismissed`, so "maybe later" re-offers next session while the book is still empty. |
| Adding | `StarterRecipesModal.importSelected` | Loops `recipesApi.create()` **sequentially, one HTTP request per recipe** — deliberately serial, because `crud.get_or_create_ingredient` resolves by name and parallel creates would race into duplicate ingredient rows. |

Consequences of that shape, all of which this design removes:

- Changing the offered recipes requires a **frontend deploy**.
- Adopted recipes carry **no provenance**: no `source_recipe_id`, no attribution, no counter.
- The pack is reachable **only** while the book is empty. A user who adds one recipe by hand
  can never see it again.
- `minutes` and `blurb` exist in the pack and are rendered in the modal, but are **never
  persisted** — `Recipe` has no column for either.
- Adding 60 recipes is 60 HTTP round-trips and 60 transactions.

### 1.2 What Part 1 already built that this design reuses

This is the single most important thing for the plan author to internalise: **most of the
machinery already exists.** Do not build parallel versions of it.

| Capability | Where it already lives |
|---|---|
| `Recipe.user_id` is **nullable** | [`backend/models.py`](../../../backend/models.py) — `_owner_fk_column()` |
| Per-user duplication with ingredient/tag namespace isolation | [`backend/recipe_copy.py`](../../../backend/recipe_copy.py) — `_duplicate()` |
| Two-pass copy including favourite sides, single commit | `recipe_copy.copy_recipe()` |
| "Does this user already hold a copy of X?" | `recipe_copy.existing_copy()` |
| Permanent attribution snapshot | `Recipe.source_recipe_id`, `source_user_id`, `source_author_username`, `source_recipe_title`, `copied_at` |
| Raw copy tally | `Recipe.copy_count` |
| Three-state visibility, with `public` guarded off | `Recipe.visibility`; validator at [`schemas.py:285-293`](../../../backend/schemas.py#L285-L293); 400 handler at [`main.py:119`](../../../backend/main.py#L119) |
| Unique, case-insensitive handles + a reserved list | `User.username`, `models.RESERVED_USERNAMES`, `ReservedUsername`, `backend/usernames.py` |
| Per-user (not per-IP) rate limiting | [`backend/ratelimit.py`](../../../backend/ratelimit.py) — `ratelimit.limiter`, registered as `app.state.share_limiter` |
| Domain-router precedent | `username_routes.py`, `share_routes.py`, `public_pages.py`, `ops_routes.py` — each owns its routes and defines its Pydantic models locally |
| Ownership scoping | [`backend/scoping.py`](../../../backend/scoping.py) — `scope()`, `owned()` |
| Idempotent startup data | `main._bootstrap()` ([`main.py:48-74`](../../../backend/main.py#L48-L74)) |

### 1.3 The problem this design solves

Promote the hardcoded client-side starter pack into a **real, server-side, curatable catalog**
that any signed-in user can browse at any time, ranked by how many users have adopted each
recipe, and managed through an admin UI rather than a deploy.

| Today | After this design |
|---|---|
| 1416-line JS constant shipped to the browser | Rows in the database, served by an API |
| Reachable only when the book is empty | Browsable any time from a sidebar entry |
| 60 sequential `POST /recipes` calls | One adopt call, one transaction |
| No provenance | Attribution snapshot + adoption count |
| Changing it = frontend deploy | Changing it = admin action |

---

## 2. Objectives

| # | Objective |
|---|---|
| O-1 | A signed-in user can browse a curated catalog of recipes at any time, not only when their book is empty. |
| O-2 | A user can add one or several catalog recipes to their own book in a single action. |
| O-3 | Catalog recipes are ranked by how many distinct users have added them, so the most-liked surface first. |
| O-4 | The catalog is not fixed: recipes can be added, edited and retired over time without a deploy. |
| O-5 | An administrator can author and curate catalog recipes through the application. |
| O-6 | The 60 recipes currently hardcoded in the frontend are preserved, moved server-side, and the frontend constant is deleted. |
| O-7 | The design is the scaffolding for a future where real users publish their own recipes into a shared catalog, without requiring a migration to get there. |

## 2.1 Non-objectives

Each of these is **explicitly out of scope**. Do not implement them, and do not leave
half-built hooks for them beyond what §18 names.

- **Any public or unauthenticated surface.** No `/r/{slug}` pages, no slugs, no `sitemap.xml`,
  no `robots.txt` changes, no SEO or JSON-LD, no OpenGraph. The catalog is authenticated-only.
- **Users publishing their own recipes.** That is Part 2 and stays deferred.
- **Ratings, reviews, comments, or any social graph.**
- **Re-syncing.** If an admin edits a catalog recipe, users who already adopted it keep their
  copy unchanged. There is no "an update is available" notion.
- **Admin user management.** No listing users, no editing users, no admin granting admin.
- **An administrative audit log.** Part 2 requires one (its `MOD-7`: actor, target, action,
  timestamp), because it governs moderation of *other people's* published content. Here the only
  administrator is the operator and the only content is their own, so there is nobody the log
  would hold accountable to anybody. It is named here so the omission reads as a decision rather
  than an oversight, and so it is picked up when Part 2 is taken on.
- **Publishing anything other than recipes.** No catalog of plans, ingredients, tags, or shopping lists.
- **Trending / time-windowed popularity.** Popularity is a lifetime distinct-adopter count.
- **Pagination of the catalog listing.** At 60 entries it is not needed; API-20 requires a
  documented cap instead, so the day it *is* needed is visible rather than a slow degradation.
- **Collections, categories, or curated "packs"** beyond the existing course and tag vocabulary.
- **Changes to the deprecated legacy `/plan` routes.** Per CLAUDE.md, no new features there.
- **Images for catalog recipes** beyond what `Recipe.image_url` already supports.

---

## 3. Relationship to Part 2, and why this is not it

Part 2 ("Public Publishing") is gated behind preconditions the project has deliberately not
met: terms of service, a privacy policy, a published takedown contact, a named person
accountable for abuse reports, and a recorded decision to accept an ongoing moderation
obligation.

This design triggers **none** of them, because the catalog contains **first-party content only**
— recipes authored by the operator, published under the operator's own name. There is no
stranger's content on any surface.

The mechanism that keeps that true is architectural, not procedural:

| ID | Requirement |
|---|---|
| P2-1 | Catalog membership **MUST** be determined solely by the presence of a `catalog_entries` row with `status = 'published'`. |
| P2-2 | Catalog recipes **MUST** keep `visibility = 'private'`. |
| P2-3 | The validator forbidding `visibility = 'public'` ([`schemas.py:285-293`](../../../backend/schemas.py#L285-L293)) **MUST NOT** be relaxed, removed, or bypassed by this work. |
| P2-4 | No route added by this design **MAY** be reachable without authentication. |
| P2-5 | `shares.py`, `share_routes.py`, `public_pages.py`, and `public_schema.py` **MUST NOT** be modified by this work, except as §19 explicitly permits. |

Deliberately rejected alternatives, recorded so they are not re-opened: reusing
`visibility = 'unlisted'` (it already means "reachable by a share-token holder", and
overloading it would force `shares.py` to distinguish two meanings of one value), and removing
the VIS-5 guard to use `visibility = 'public'` (that *is* Part 2, and takes on its obligations
for content that does not need them).

The payoff for O-7 is that separating **authorship** from **curation** means a future
user-published recipe joins the catalog by inserting one `catalog_entries` row — no ownership
transfer, no migration, and no change to the listing query. It also means "a user made a recipe
public" and "a recipe is in the catalog" stay independent, so the catalog can never silently
become an unmoderated firehose.

---

## 4. The system account

Catalog recipes are owned by a single dedicated `User` row.

| ID | Requirement |
|---|---|
| SYS-1 | `users` **MUST** gain `is_system BOOLEAN NOT NULL DEFAULT false`. |
| SYS-2 | At most one row **MUST** be able to have `is_system = true`, enforced by a **unique partial index** (`WHERE is_system`), not by application code. |
| SYS-3 | The system account's handle **MUST** be `mealplanner` and its email `mealplanner@localhost`. |
| SYS-4 | `mealplanner` **MUST** be added to `models.RESERVED_USERNAMES` so no real person can claim it. |
| SYS-5 | The system account **MUST** have `hashed_password = NULL`, `google_sub = NULL`, `auth_provider = 'local'`, and `email_verified = false`, so no login path exists for it. |
| SYS-6 | Code **MUST** resolve the system account by `is_system = true`. It **MUST NOT** resolve it by the handle literal `'mealplanner'`, by email, or by a hardcoded id. |
| SYS-7 | The system account **MUST NOT** appear in any user-facing list of people, and its handle **MUST NOT** be returned by any API response body. |
| SYS-8 | The system account **MUST** own its own `Ingredient` and `Tag` rows, seeded via the existing `seed_system_ingredients` / `seed_system_tags`, because both are per-user (`uq_ingredient_user_name`, `uq_tag_user_name`). |
| SYS-9 | Deleting the system account **MUST NOT** be possible through any API. |
| SYS-10 | Creating the system account **MUST** bypass the reserved-handle check. `crud.create_user` does not consult the reserved list (the check lives at the route layer, in `usernames.is_available`), so passing `username='mealplanner'` works today — **no guard MUST be added to `crud.create_user`**, or SYS-4 would make the system account uncreatable. |
| SYS-11 | The system account's email **MUST NOT** be validated through a Pydantic `EmailStr` path. `mealplanner@localhost` is created by constructing the model directly, which is what `_bootstrap` and the seed scripts already do. |
| SYS-12 | The system account **MUST** be created with `username_changed_at` set (i.e. `crud.create_user(username='mealplanner')`, which records it as chosen). Leaving it `NULL` would mark the handle "system-assigned, unconfirmed" (the `D-7` decision, documented on `User.username_changed_at` and `User.username_confirmed` in `backend/models.py` — note `D-7` is an implementation-plan id used in code comments, not defined in either sharing spec) and is a state that only exists to force a login through handle selection — which this account never does. |

**Rationale for SYS-6**: the handle is expected to change. An `is_system` flag makes that a
one-row `UPDATE` that breaks nothing. Resolving by handle would scatter a string literal that a
rename silently invalidates.

**Rationale for SYS-2 as a database constraint**: two system accounts would split the catalog
in half with no error anywhere. A unique partial index makes that state unrepresentable.

---

## 5. Data model

| ID | Requirement |
|---|---|
| DM-1 | A new table `catalog_entries` **MUST** be created with exactly these columns: `recipe_id INTEGER PRIMARY KEY REFERENCES recipes(id) ON DELETE CASCADE`; `status VARCHAR NOT NULL DEFAULT 'published'`; `published_at TIMESTAMP NOT NULL DEFAULT now()`; `retired_at TIMESTAMP NULL`. |
| DM-2 | `recipe_id` **MUST** be the primary key. A surrogate key **MUST NOT** be used: a recipe is in the catalog at most once, and the schema should say so rather than leave it to a unique constraint plus application care. |
| DM-3 | A `CHECK` constraint named `ck_catalog_entry_status` **MUST** restrict `status` to `('published', 'retired')`. |
| DM-4 | A `CHECK` constraint named `ck_catalog_entry_retired_all_or_nothing` **MUST** enforce `(status = 'retired') = (retired_at IS NOT NULL)`, mirroring the all-or-nothing pattern already used by `ck_meal_leftover_source_all_or_nothing`. |
| DM-5 | An index **MUST** be added on `recipes.source_recipe_id`. The adoption count (§7) groups by it on every catalog listing, and without the index that is a sequential scan of every recipe in the database. |
| DM-6 | `users` **MUST** gain `is_admin BOOLEAN NOT NULL DEFAULT false` (see §9). |
| DM-7 | `Recipe` **MUST NOT** gain any new column. In particular the pack's `minutes` and `blurb` are **dropped** (§11 explains what replaces them). |
| DM-8 | `catalog_entries` **MUST NOT** carry a `user_id`. The owning user is reachable through `recipes.user_id`; duplicating it would permit the two to contradict each other, the same reasoning `recipe_tag_table` and `recipe_favorite_side_table` already follow. |
| DM-9 | The `CatalogEntry` model **MUST** be declared in `backend/models.py` alongside the other models, with a `relationship` to `Recipe`. |
| DM-10 | `Recipe` **MUST** gain a `catalog_entry` relationship (`uselist=False`) so a recipe can be asked whether it is catalogued without a second query. |

**Rationale for DM-7**: `minutes` and `blurb` are catalog *presentation* metadata, not facts
about a recipe the user owns. Adding them to `Recipe` would drag in migrations, `schemas.py`,
the recipe form, the recipe card, import/export, and `seed_testing_data.py` for a field the
app does not otherwise use. Putting them on `catalog_entries` was also rejected: the catalog
detail view (UI-7) shows the real ingredients and procedure, which is strictly better
information than a one-line blurb.

---

## 6. The catalog service

| ID | Requirement |
|---|---|
| CAT-1 | A new module `backend/catalog.py` **MUST** hold all catalog domain logic. Routers **MUST NOT** contain it. |
| CAT-2 | `catalog.py` **MUST** expose: `system_user(session)`, `list_published(session, *, course, tags, query, sort)`, `adoption_counts(session, recipe_ids)`, `adopt(session, user, recipe_ids)`, `publish(session, recipe)`, `retire(session, recipe)`, and `export_catalog(session)`. |
| CAT-3 | `system_user()` **MUST** raise a clear, named exception when no `is_system` row exists, rather than returning `None` and letting callers fail later with an obscure error. |
| CAT-4 | `list_published()` **MUST** return only entries whose `status = 'published'`. |
| CAT-5 | `list_published()` **MUST** eager-load each recipe's ingredients and tags, so rendering a listing of 60 recipes is not 120 extra queries. |
| CAT-6 | `publish()` **MUST** be idempotent: publishing an already-published entry is a no-op that does not change `published_at`. |
| CAT-7 | `publish()` on a previously retired entry **MUST** set `status = 'published'`, clear `retired_at`, and **MUST NOT** change the original `published_at`. |
| CAT-8 | `retire()` **MUST** set `status = 'retired'` and `retired_at = now()`. It **MUST NOT** delete the `catalog_entries` row, and **MUST NOT** delete or modify the `Recipe` row. |
| CAT-9 | `publish()` **MUST** reject a recipe not owned by the system account, with a `PermissionError`. (Curating another user's recipe is Part 2 territory; the seam exists but the door stays shut.) |
| CAT-10 | `publish()` **MUST** reject a recipe with no title, no ingredients, or no procedure. |
| CAT-11 | `catalog.py` **MUST NOT** import from `main.py`, any router module, or `frontend-v2`. |

### 6.1 Retirement semantics

| ID | Requirement |
|---|---|
| RET-1 | A retired entry **MUST** disappear from the catalog listing and the catalog detail endpoint for every user, including administrators browsing the user-facing page. |
| RET-2 | Users who already adopted a retired recipe **MUST** keep their copy entirely intact and editable. It is their own `Recipe` row and always was. |
| RET-3 | No notification, banner, badge, or marker **MUST** be shown on an adopted copy of a retired recipe. Nothing about the user's recipe changed. |
| RET-4 | The adoption count of a retired entry **MUST** be preserved, so re-publishing restores the entry with its history. |
| RET-5 | Hard-deleting a catalog recipe **MUST NOT** be offered in the admin UI. Retirement is the only removal mechanism. |

---

## 7. Popularity

| ID | Requirement |
|---|---|
| POP-1 | "How many users added this recipe" **MUST** be derived from existing data: `COUNT(DISTINCT recipes.user_id) WHERE recipes.source_recipe_id = <catalog recipe id>`. |
| POP-2 | No new table and no denormalised counter column **MUST** be introduced for it. |
| POP-3 | The count **MUST** exclude the system account itself. |
| POP-4 | The count for a whole listing **MUST** be obtained in **one** grouped query, not one query per entry. |
| POP-5 | The count **MUST** be exposed as `adoption_count` on each catalog listing row and on the detail response. |
| POP-6 | `Recipe.copy_count` **MUST NOT** be used as the popularity signal. It is a lifetime tally that never decrements and counts copies rather than users. |
| POP-7 | The default sort order of the catalog listing **MUST** be `adoption_count` descending, with recipe title ascending as a deterministic tie-break. |

**Why derivation rather than a table or a counter**: `recipe_copy` already stamps
`source_recipe_id` on every copy, so the adoption set is *already in the database*. Deriving it
means the count is correct by construction — a user who deletes their copy drops out
automatically, and re-adding cannot double-count because `existing_copy()` already detects a
prior copy. A `catalog_adoptions` table would be a second source of truth that can drift from
the copies it claims to describe. If the grouped query ever becomes slow, a denormalised
counter can be added later **without changing semantics**, which is not true in reverse.

---

## 8. Adopting a catalog recipe

| ID | Requirement |
|---|---|
| ADO-1 | Adopting **MUST** create a copy of the catalog recipe owned by the adopting user, following the existing `recipe_copy` field allowlist. |
| ADO-2 | Adopting **MUST NOT** copy the recipe's favourite sides. Exactly one `Recipe` row is created per adopted recipe. |
| ADO-3 | `recipe_copy.copy_recipe()`'s existing two-pass behaviour (which *does* copy favourite sides, per Part 1 CP-6) **MUST NOT** be changed. User-to-user sharing keeps it. |
| ADO-4 | To satisfy ADO-2 and ADO-3 together, `recipe_copy._duplicate()` **MUST** be promoted to a public `recipe_copy.duplicate()` and called directly by `catalog.adopt()`. `copy_recipe()` **MUST** continue to use it for its first pass. |
| ADO-5 | `POST /catalog/adopt` **MUST** accept a list of recipe ids and adopt all of them in **one** database transaction, with exactly one `commit()`. |
| ADO-6 | A partially-failed batch **MUST NOT** be committed. Either every requested recipe is adopted or none is. |
| ADO-7 | Adopting a recipe the user already holds a copy of **MUST** be a silent no-op for that recipe, detected with `recipe_copy.existing_copy()`. The response **MUST** report it as skipped rather than failing the batch. |
| ADO-8 | The copy **MUST** carry the full attribution snapshot: `source_recipe_id`, `source_user_id`, `source_author_username`, `source_recipe_title`, `copied_at`. POP-1 depends on `source_recipe_id`, so it is not optional. |
| ADO-9 | The copy **MUST** have `visibility = 'private'` and `copy_count = 0`, as `_duplicate()` already does. |
| ADO-10 | The copy **MUST NOT** inherit `score`, `date_last_consumed`, or `date_last_rejected`. Part 1 CP-7 forbids planner history crossing accounts, and seeding a new user's planner with the operator's habits is exactly what it protects against. |
| ADO-11 | Ingredients **MUST** be resolved with `crud.get_or_create_ingredient(session, None, name, adopter.id, ...)` — id always `None`, so a copy can only ever bind to the adopter's own ingredient rows (Part 1 CP-3). |
| ADO-12 | Tags **MUST** be resolved with `crud.get_or_create_tag(session, name, adopter.id)`. |
| ADO-13 | Adopting **MUST** be rate-limited **per user** using `ratelimit.limiter`, not the per-IP limiter in `main`. A limited route must accept `request: Request` even if it ignores it. |
| ADO-14 | Adopting a recipe that is not a published catalog entry **MUST** return 404, whether it is retired, never catalogued, or another user's private recipe. The endpoint **MUST NOT** become a general-purpose recipe copier. |
| ADO-15 | The batch size accepted by `POST /catalog/adopt` **MUST** be bounded by a named constant in `catalog.py` (not a literal at the route), and the bound **MUST** be at least 100 — comfortably above the 60 the catalog ships with, so "select all and add" keeps working as the catalog grows. |
| ADO-16 | Adopting **SHOULD** increment `Recipe.copy_count` on the source, for consistency with `copy_recipe`. It is not the ranking signal (POP-6) and nothing user-facing reads it here. |

---

## 9. Administration

| ID | Requirement |
|---|---|
| ADM-1 | `users` **MUST** gain `is_admin BOOLEAN NOT NULL DEFAULT false`. |
| ADM-2 | **No API route, service function, or startup path MUST ever write `is_admin`.** It is granted exclusively by direct SQL against the database. This makes privilege escalation over HTTP impossible by construction rather than by guard. |
| ADM-3 | A dependency `auth_users.require_admin` **MUST** be added, building on `get_current_user`, returning 403 for a non-admin and 401 for an unauthenticated caller. |
| ADM-4 | Every admin route **MUST** depend on `require_admin`. |
| ADM-5 | `schemas.UserOut` **MUST** expose `is_admin: bool = False`, so `GET /auth/me` tells the SPA whether to render admin controls. |
| ADM-6 | Admin routes **MUST** live in a new `backend/catalog_admin_routes.py`, wired with `include_router` in `main.py` alongside the existing routers, and defining their Pydantic models locally per CLAUDE.md. |
| ADM-7 | An admin **MUST** be able to create a catalog recipe, edit it, and publish or retire it. Recipes so created **MUST** be owned by the system account (SYS-6 resolution). |
| ADM-8 | An admin **MUST NOT** be able to promote a recipe owned by any account other than the system account (CAT-9). |
| ADM-9 | Admin privilege **MUST** grant nothing beyond catalog authoring and curation. It **MUST NOT** grant access to other users' recipes, plans, ingredients, tags, shares, or accounts. |
| ADM-10 | An admin's own recipe book, plans and data **MUST** behave exactly as any other user's. |
| ADM-11 | Admin write routes **MUST** be rate-limited per user via `ratelimit.limiter`. |
| ADM-12 | Admin ingredient resolution **MUST** scope to the **system account**, not to the admin's own account, so authoring a catalog recipe never creates or mutates rows in the admin's personal pantry. |

### 9.1 Catalog export

The alpha runs with **no database backups** (a recorded project decision). The catalog is
curated content that would otherwise exist only in that database.

| ID | Requirement |
|---|---|
| EXP-1 | `GET /admin/catalog/export` **MUST** return the whole catalog — every entry, published and retired — as JSON. |
| EXP-2 | The export **MUST** contain, per entry: title, course, servings, procedure, `bulk_prep`, tags by name, ingredients by name with quantity and unit, `status`, `published_at`, `retired_at`. |
| EXP-3 | The export **MUST NOT** contain user data of any kind: no adopter identities, no adoption counts, no emails, no handles. |
| EXP-4 | The export **MUST** be a **superset** of `backend/data/catalog_pack.json`'s shape (§11): the INIT-3 fields in the same spelling, plus `status`, `published_at` and `retired_at`. |
| EXP-5 | The pack loader (INIT-8) **MUST** accept and ignore the three extra fields, so an export file can be dropped in as a pack file to repopulate an empty catalog. Every entry so loaded is created `published` regardless of the `status` in the file — restoring a retired entry as retired is not a requirement, and silently creating invisible entries would be worse than not restoring them. |

---

## 10. API

All routes require authentication (P2-4). Paths are given exactly.

### 10.1 User-facing — `backend/catalog_routes.py`

| ID | Requirement |
|---|---|
| API-1 | `GET /catalog/recipes` **MUST** return published catalog entries. Query parameters: `course` (repeatable), `tags` (repeatable, AND semantics matching the existing recipe filters), `q` (case-insensitive substring match on title), `sort` (`popular` \| `title`, default `popular`). |
| API-2 | Each row **MUST** carry the recipe's id, title, course, servings, `bulk_prep`, tags, ingredients (name, quantity, unit), `image_url`, plus `adoption_count` and `in_my_book`. |
| API-3 | `in_my_book` **MUST** be true exactly when the calling user already holds a copy whose `source_recipe_id` is this recipe. It **MUST** be computed for the whole listing in one query, not one per row. |
| API-4 | The listing **MUST NOT** include the recipe's `procedure`. Bodies stay small; the detail endpoint serves it. |
| API-5 | `GET /catalog/recipes/{recipe_id}` **MUST** return the full recipe including `procedure`, `adoption_count` and `in_my_book`. It **MUST** return 404 for anything that is not a published catalog entry. |
| API-6 | `POST /catalog/adopt` **MUST** accept `{"recipe_ids": [int, ...]}` and return the created recipe ids and the skipped ids (ADO-7), subject to §8 in full. |
| API-7 | No catalog response **MUST** expose the system account's handle, email, or id (SYS-7). |
| API-8 | Catalog responses **MUST NOT** expose `score`, `date_last_consumed`, `date_last_rejected`, `copy_count`, or `visibility` of the catalog recipe. A catalog row is a menu item, not a recipe record. |
| API-20 | `GET /catalog/recipes` **MAY** return every published entry unpaginated at the sizes this design ships with (60), but it **MUST** apply a hard server-side cap as a named constant and **MUST** document that pagination is the intended next step past it. An uncapped listing that silently grows into a multi-megabyte response is not acceptable, and pagination is explicitly not in scope here (§2.1). |

### 10.2 Admin — `backend/catalog_admin_routes.py`

| ID | Requirement |
|---|---|
| API-9 | `GET /admin/catalog/recipes` **MUST** list every entry, published **and** retired, with `status` and `adoption_count`. |
| API-10 | `POST /admin/catalog/recipes` **MUST** create a recipe owned by the system account and, by default, a `published` catalog entry for it. |
| API-11 | `PUT /admin/catalog/recipes/{recipe_id}` **MUST** update a system-owned catalog recipe. |
| API-12 | `POST /admin/catalog/recipes/{recipe_id}/publish` and `.../retire` **MUST** perform CAT-6/7 and CAT-8 respectively. |
| API-13 | `GET /admin/catalog/export` **MUST** behave per §9.1. |
| API-14 | There **MUST NOT** be a route that deletes a catalog recipe or its entry (RET-5). |
| API-15 | Every route in §10.2 **MUST** return 403 for an authenticated non-admin and 401 for an unauthenticated caller. |

### 10.3 Existing endpoints

| ID | Requirement |
|---|---|
| API-16 | `schemas.RecipeOut` **MUST** gain `from_library: bool = False`, true when the recipe's `source_user_id` is the system account's id. This is what lets the frontend render the attribution line (UI-10) without ever learning the system handle. |
| API-17 | `GET /recipes` and `GET /recipes/{id}` **MUST** continue to return only the caller's own recipes. The system account's recipes **MUST NOT** leak into them. |
| API-18 | `schemas.UserOut` **MUST** gain `is_admin` (ADM-5). |
| API-19 | No change **MUST** be made to any `/plan` route (CLAUDE.md: deprecated, no new features). |

---

## 11. Initial population

| ID | Requirement |
|---|---|
| INIT-1 | The 60 recipes currently in `frontend-v2/src/constants/starterRecipes.js` **MUST** be ported to `backend/data/catalog_pack.json`, alongside the existing `system_ingredients.json` and `system_tags.json`. |
| INIT-2 | All 60 **MUST** be ported: 26 `main`, 20 `side`, 14 `first-course`. A test **MUST** assert the count and the per-course breakdown so a silent loss during porting fails CI. |
| INIT-3 | Each entry **MUST** carry: `title`, `course`, `servings`, `bulk_prep`, `tags`, `procedure`, and `ingredients` as `{name, quantity, unit}`. |
| INIT-4 | `minutes` and `blurb` **MUST NOT** be ported (DM-7). |
| INIT-5 | Every ingredient `name` in the pack **MUST** already exist in `backend/data/system_ingredients.json`, and a test **MUST** enforce it — preserving the invariant the current frontend tests enforce, so adoption reuses real seasonality and conversions instead of inventing all-year defaults. |
| INIT-6 | Every tag in the pack **MUST** be one of the system tags in `backend/data/system_tags.json`, enforced by a test. The pack introduces no tag vocabulary. |
| INIT-7 | Quantities **MUST** be ported verbatim together with their `servings` basis. The pack's amounts are written per person unless the entry states otherwise, and `Recipe.servings` is the basis readers divide by — porting a quantity without its basis changes what it means. |
| INIT-8 | Population **MUST** be performed by an idempotent block in `main._bootstrap()`, following the precedent already there for system tags and reserved usernames. |
| INIT-9 | Population **MUST** create the system account if absent, seed its tags and ingredients (SYS-8), create the 60 recipes, and create a `published` entry for each. |
| INIT-10 | Population **MUST** run only when the system account holds **zero** `catalog_entries` rows, counting retired ones. Once the catalog is non-empty the pack file **MUST NOT** be re-applied. |
| INIT-11 | Population **MUST NOT** update, overwrite, or reconcile an existing catalog recipe under any circumstances. An admin edit surviving a restart is a hard requirement. |
| INIT-12 | The Alembic revision **MUST** create schema only. The 60 recipes **MUST NOT** be inserted by a migration script: a data migration would need to reimplement ingredient and tag resolution against a schema snapshot, and would re-run against the wrong future schema. |
| INIT-13 | Population **MUST** be idempotent and safe to run on every application start, as `_bootstrap` is today. |

**Why `_bootstrap` rather than a standalone script**: `_bootstrap` already establishes the
pattern for idempotent startup data, already runs before the first request, and needs no
operator action on deploy. A script would require someone to remember to run it on every new
environment, including CI and `docker compose up`.

---

## 12. Frontend

All UI work **MUST** follow [`MEAL_PLANNER_DESIGN_GUIDE.md`](../../../MEAL_PLANNER_DESIGN_GUIDE.md),
per CLAUDE.md.

| ID | Requirement |
|---|---|
| UI-1 | A new route `/discover` **MUST** be added in [`App.jsx`](../../../frontend-v2/src/App.jsx) inside the authenticated route group. |
| UI-2 | A sidebar entry labelled **"Discover"** **MUST** be added to the `NAV` array in [`Sidebar.jsx:13-18`](../../../frontend-v2/src/components/Sidebar.jsx#L13-L18), and to `NavDrawer` if it maintains its own list. It **SHOULD** sit directly after "Recipes". |
| UI-3 | A new page `frontend-v2/src/pages/DiscoverPage.jsx` **MUST** implement the catalog. |
| UI-4 | A new API module `frontend-v2/src/api/catalogApi.js` **MUST** wrap the endpoints, going through `api/client.js`'s `request()` helper like every other resource module. |
| UI-5 | The page **MUST** support sorting by most-added (default) and filtering by course and tags, reusing `RecipeFilters`, `RecipeSort` and `ActiveFilterChips` rather than reimplementing them. |
| UI-6 | The page **MUST** provide free-text search on recipe title. |
| UI-7 | A user **MUST** be able to open a catalog recipe and read its full ingredients and procedure before adding it. |
| UI-8 | The page **MUST** support multi-select with a single "Add N recipes" action, and the count in the button **MUST** equal the number of recipes that will actually be created. |
| UI-9 | A recipe already in the user's book **MUST** show an "In your book" state instead of an add control, and **MUST NOT** be selectable for adding. |
| UI-10 | [`AttributionLine.jsx`](../../../frontend-v2/src/components/AttributionLine.jsx) **MUST** render **"From the recipe library"** when `recipe.from_library` is true, instead of its current `Adapted from {title} by @{username}` form. It **MUST NOT** render the system handle. |
| UI-11 | Admin controls **MUST** be rendered on `/discover` only when `GET /auth/me` reports `is_admin`. A non-admin **MUST** see no trace of them. |
| UI-12 | Admin controls **MUST** cover: create a catalog recipe, edit one, publish, retire, view retired entries, and download the export. |
| UI-16 | Retired entries **MUST** be reached through a distinct admin view or toggle backed by `GET /admin/catalog/recipes` (API-9) — **never** by relaxing the user-facing listing, which RET-1 requires to hide retired entries from administrators too. The two listings are separate endpoints and separate requests. |
| UI-13 | The adoption count **MUST** be displayed on each catalog card as an aggregate only — never who adopted it. |
| UI-14 | The page **MUST** handle its empty state (no published entries) and its error state without a blank screen. |
| UI-15 | Adding recipes **MUST** give visible progress or completion feedback, and on failure **MUST** say what failed and leave the selection intact so the action can be retried. |

### 12.1 Removing the starter pack

| ID | Requirement |
|---|---|
| RM-1 | `frontend-v2/src/constants/starterRecipes.js` **MUST** be deleted. |
| RM-2 | `frontend-v2/src/components/StarterRecipesModal.jsx` **MUST** be deleted. |
| RM-3 | `frontend-v2/src/constants/__tests__/starterRecipes.test.js` and `frontend-v2/src/components/__tests__/StarterRecipesModal.test.jsx` **MUST** be deleted. |
| RM-4 | The starter-pack machinery in `RecipesPage.jsx` **MUST** be removed: the lazy import (line 114), `STARTER_DISMISSED_KEY` (line 116), the `showStarter` state (line 130), the empty-book trigger (line 170), the modal render (lines ~720-726), and the `sessionStorage` dismissal write. |
| RM-5 | `PageTour`'s gate at `RecipesPage.jsx:356` (`enabled={loaded && !showStarter}`) **MUST** be simplified to drop the `showStarter` term, which no longer exists. The tour **MUST** still work on a brand-new empty account. |
| RM-6 | `RecipesPage`'s empty state **MUST** become a call to action pointing at `/discover` — the user's route to a populated book. |
| RM-7 | The filtered-empty state at `RecipesPage.jsx:540` (`loaded && recipes.length > 0 && filteredRecipes.length === 0`) **MUST** keep its `recipes.length > 0` guard — it is what distinguishes "no results for your filter" from "your book is empty", and RM-6 now owns the second case. Its **comment**, which justifies the guard by the starter-pack offer that no longer exists, **MUST** be rewritten to cite RM-6 instead. |
| RM-8 | The `frontend-v2` test suite **MUST** pass with no reference to the deleted modules remaining anywhere in the repository, enforced by a grep-style assertion or by the suite failing on a dangling import. |
| RM-9 | Nothing **MUST** remain that adds catalog recipes by looping `recipesApi.create()`. `POST /catalog/adopt` is the only adoption path. |

---

## 13. Errors and edge cases

| ID | Requirement |
|---|---|
| ERR-1 | Adopting an id that is not a published entry: 404, whole batch rejected (ADO-14, ADO-6). |
| ERR-2 | Adopting an empty `recipe_ids` list: 400 with a clear message, not a silent success. |
| ERR-3 | Adopting more than the §8 bound: 400 naming the limit. |
| ERR-4 | Adopting when every requested recipe is already held: 200 with all ids reported skipped and nothing created. |
| ERR-5 | Any catalog route when no `is_system` row exists: a 500 whose log line names the missing system account (CAT-3), not an `AttributeError` on `None`. |
| ERR-6 | An admin publishing a recipe failing CAT-10's completeness check: 400 naming the missing part. |
| ERR-7 | An admin publishing a recipe owned by someone else: 403 (CAT-9, ADM-8). |
| ERR-8 | A non-admin calling any `/admin/*` route: 403. Unauthenticated: 401 (API-15). |
| ERR-9 | An adopted recipe whose source catalog recipe is later deleted directly in the database: the copy **MUST** survive with its attribution snapshot, because `source_recipe_id` is `ON DELETE SET NULL`. Its contribution to that entry's count is lost, which is correct — the entry is gone. |
| ERR-10 | A user deleting their adopted copy **MUST** decrement that recipe's adoption count on the next read, with no extra bookkeeping (POP-1). |
| ERR-11 | `q` containing SQL wildcards (`%`, `_`) **MUST** be treated as literal characters, not as patterns. |
| ERR-12 | A concurrent double-submit of the same adopt batch **MUST NOT** produce two copies. ADO-7's `existing_copy()` check plus the single transaction is the mechanism; a test **MUST** cover the same batch submitted twice in sequence. |

---

## 14. Migrations

CLAUDE.md's migration rules apply in full and are not restated. Feature-specific obligations:

| ID | Requirement |
|---|---|
| MIG-1 | One Alembic revision **MUST** be created in the same commit as the model changes, with `down_revision = 'a1d4f7b2c903'` (the current head) unless another revision has landed first. |
| MIG-2 | The revision **MUST** create `catalog_entries` with both `CHECK` constraints **explicitly named** (`ck_catalog_entry_status`, `ck_catalog_entry_retired_all_or_nothing`). An unnamed `CHECK` has no name in the metadata to match the reflected one, so autogenerate proposes dropping it on every subsequent migration — the trap `meals_meal_number_check` already documents in `models.py`. |
| MIG-3 | The revision **MUST** add `users.is_system` and `users.is_admin`, both `NOT NULL` with a `server_default` of false, so existing rows are valid without a backfill step. |
| MIG-4 | The revision **MUST** create the unique partial index enforcing SYS-2 (`postgresql_where`). |
| MIG-5 | The revision **MUST** create the index on `recipes.source_recipe_id` (DM-5). |
| MIG-6 | The generated script **MUST** be read and corrected by hand before committing. Autogenerate cannot see renames and does not compare `CHECK` expressions. |
| MIG-7 | `downgrade()` **MUST** be implemented and **MUST** reverse everything `upgrade()` does. |
| MIG-8 | The revision **MUST NOT** insert any recipe data (INIT-12). |
| MIG-9 | `backend/tests/test_migrations.py` **MUST** pass: it builds a database from the migrations alone and fails on any disagreement with the models. |
| MIG-10 | `backend/migrations/README.md` **MUST** be updated with this revision, per the changelog practice it documents. |

---

## 15. Seed script (mandatory per CLAUDE.md)

CLAUDE.md: *"whenever the database schema or domain model changes … `seed_testing_data.py`
MUST be updated in the same change so the seeded data stays coherent."* This change adds two
columns and a table, so the obligation applies.

| ID | Requirement |
|---|---|
| SEED-1 | `backend/scripts/seed_testing_data.py` **MUST** create the system account with `is_system = true` and the SYS-3/SYS-5 field values. |
| SEED-2 | It **MUST** seed the system account's own tags and ingredients (SYS-8). |
| SEED-3 | It **MUST** create catalog recipes owned by the system account and `published` catalog entries for them, drawing on the same in-file catalogue it already uses so the dataset stays coherent. |
| SEED-4 | It **MUST** include at least one **retired** entry, so the retired path is represented in a seeded database. |
| SEED-5 | It **MUST** create adoptions — recipes owned by demo users with `source_recipe_id` pointing at catalog recipes — with **differing** counts across entries, so the popularity sort is visibly exercised rather than a flat list of zeros. |
| SEED-6 | It **MUST** mark exactly one demo account `is_admin = true`, so the admin UI is reachable in a seeded environment, and **MUST** state in a comment which account it is. |
| SEED-7 | It **MUST** continue to refuse to run without `ALLOW_DESTRUCTIVE_SEED=1`. |
| SEED-8 | `backend/scripts/seed_user_data.py` **MUST** be reviewed and updated if the new columns make its `User` / `Recipe` construction invalid. |
| SEED-9 | `docker compose up` **MUST** still arrive at a clean, fully-populated database including a populated catalog. |

---

## 16. Privacy and security

| ID | Requirement |
|---|---|
| PRV-1 | The adoption count **MUST** be exposed as an aggregate only. No endpoint, response, or UI **MUST** reveal which users adopted a recipe, consistent with Part 1 AT-7. |
| PRV-2 | No catalog endpoint **MUST** return any other user's data: no emails, no handles, no recipe content belonging to anyone but the system account and the caller. |
| PRV-3 | The system account's handle, email and id **MUST NOT** appear in any API response body (SYS-7). |
| PRV-4 | `is_admin` **MUST NOT** be writable through any HTTP path (ADM-2). A test **MUST** attempt to set it via every user-facing update endpoint and assert it is ignored. |
| PRV-5 | Admin routes **MUST NOT** be discoverable as functional by a non-admin: a 403 must not differ in body or timing in a way that reveals whether a resource exists. |
| PRV-6 | `POST /catalog/adopt` **MUST NOT** be usable to copy an arbitrary recipe by id (ADO-14). |
| PRV-7 | No unauthenticated surface **MUST** be added (P2-4). |
| PRV-8 | The export **MUST NOT** contain user data (EXP-3). |

---

## 17. Testing

Per CLAUDE.md, implementation follows **test-driven development**: the test comes first.
Backend tests run from `backend/` with `pytest`; a local Postgres is required
(`docker start mp_test_pg`). Frontend tests run from `frontend-v2/` with `npm run test`.

| ID | Requirement |
|---|---|
| TST-1 | Backend tests **MUST** cover: system-account resolution and the SYS-2 single-row guarantee; publish/retire/re-publish including CAT-6 and CAT-7; filtering, search and both sort orders; the adoption count including exclusion of the system account and the decrement-on-delete behaviour (ERR-10); `in_my_book`; batch adopt in one transaction; ADO-2 (no sides copied); ADO-7 skip; ADO-6 all-or-nothing; ADO-10 (no planner history); ADO-11/12 namespace isolation; every case in §13; and `require_admin` returning 403/401. |
| TST-2 | A test **MUST** assert that adopting a catalog main dish which *has* favourite sides creates exactly one recipe (ADO-2), and a separate test **MUST** assert `copy_recipe()` still copies sides (ADO-3). Together they pin the two behaviours apart. |
| TST-3 | A test **MUST** assert the pack's integrity: the 60-recipe count and per-course breakdown (INIT-2), every ingredient name present in `system_ingredients.json` (INIT-5), every tag present in `system_tags.json` (INIT-6). |
| TST-4 | A test **MUST** assert INIT-10/INIT-11: running the bootstrap twice does not duplicate entries, and an edited catalog recipe is not reverted by a second bootstrap. |
| TST-5 | A test **MUST** assert P2-3: `visibility = 'public'` is still rejected, and every catalog recipe is `private`. |
| TST-6 | A test **MUST** assert PRV-4: `is_admin` cannot be set through any user-facing endpoint. |
| TST-7 | A test **MUST** assert multi-user isolation for the catalog, in the spirit of the existing `tests/test_multiuser_isolation.py`: user A's adoption is invisible to user B except through the aggregate count. |
| TST-8 | Frontend tests **MUST** cover `DiscoverPage`: listing, filtering, search, sort, selection, the "In your book" state, the add action's count, and the admin controls appearing only for `is_admin`. |
| TST-9 | A frontend test **MUST** cover `AttributionLine`'s `from_library` branch (UI-10) alongside its existing behaviour. |
| TST-10 | `backend/tests/test_app_wiring.py` **MUST** be extended to assert the two new routers are included. |
| TST-11 | `backend/tests/test_architecture_guards.py` **MUST** be extended to assert CAT-11 (`catalog.py` imports no router and no `main`). |
| TST-12 | `backend/tests/test_migrations.py` **MUST** pass unchanged in intent (MIG-9). |
| TST-13 | `flake8 .` **MUST** pass from `backend/`. New backend code outside the excluded directories must lint clean at max line length 120. |
| TST-14 | `npm run lint` **MUST** pass from `frontend-v2/`. |

---

## 18. Forward compatibility

These are the seams that make O-7 true. Each **MUST** be respected; none **MUST** be built out.

| ID | Requirement |
|---|---|
| FC-1 | Catalog membership is a `catalog_entries` row and nothing else (P2-1). A future user-published recipe joins by inserting one row — no ownership transfer, no migration, no change to the listing query. |
| FC-2 | `CAT-9`'s restriction to system-owned recipes **MUST** be a single, clearly-commented check in `catalog.py`, so lifting it later is one edit rather than an audit. |
| FC-3 | The adoption count **MUST NOT** assume the source is the system account. `COUNT(DISTINCT user_id) BY source_recipe_id` works identically for a user-published source. |
| FC-4 | `UI-10`'s attribution branch **MUST** be a branch, not a replacement: when a real user's recipe is adopted, `AttributionLine`'s existing `@handle` form **MUST** still render. |
| FC-5 | `catalog.py`'s `publish()` / `retire()` **MUST** be callable by something other than the admin routes without modification, so a future self-service publish flow reuses them. |
| FC-6 | `is_system` **MUST** stay the sole means of identifying the system account (SYS-6), so the handle can be renamed freely. |
| FC-7 | Nothing in this design **MUST** depend on there being exactly one catalog. If a second curated set is ever wanted, it is a column on `catalog_entries`, not a rewrite. |
| FC-8 | `catalog_entries.published_at` **MUST** be preserved across retire/re-publish (CAT-7), so a future "recently added" sort has a trustworthy field. |

---

## 19. File inventory

Everything the implementation touches. Paths are relative to the repository root.

### Backend — new

| File | Purpose |
|---|---|
| `backend/catalog.py` | Domain service (§6). No route handlers, no HTTP types. |
| `backend/catalog_routes.py` | User-facing router (§10.1). Local Pydantic models. |
| `backend/catalog_admin_routes.py` | Admin router (§10.2). Local Pydantic models. |
| `backend/data/catalog_pack.json` | The 60 ported recipes (§11). |
| `backend/migrations/versions/<rev>_system_recipe_catalog.py` | Schema only (§14). |
| `backend/tests/test_catalog*.py` | §17. |

### Backend — modified

| File | Change |
|---|---|
| `backend/models.py` | `CatalogEntry`; `User.is_system`, `User.is_admin`; unique partial index; `Recipe.catalog_entry`; `mealplanner` added to `RESERVED_USERNAMES`. |
| `backend/schemas.py` | `UserOut.is_admin`; `RecipeOut.from_library`. The visibility validator at lines 285-293 is **not** touched (P2-3). |
| `backend/recipe_copy.py` | `_duplicate` → public `duplicate()` (ADO-4). `copy_recipe()`'s behaviour unchanged (ADO-3). |
| `backend/auth_users.py` | `require_admin` (ADM-3). |
| `backend/main.py` | Two `include_router` calls; catalog population inside `_bootstrap` (INIT-8); `from_library` populated on recipe responses. No other route changes. |
| `backend/scripts/seed_testing_data.py` | §15. **Mandatory.** |
| `backend/scripts/seed_user_data.py` | Review per SEED-8. |
| `backend/migrations/README.md` | MIG-10. |
| `backend/tests/test_app_wiring.py` | TST-10. |
| `backend/tests/test_architecture_guards.py` | TST-11. |

### Frontend — new

| File | Purpose |
|---|---|
| `frontend-v2/src/pages/DiscoverPage.jsx` | The catalog page (§12). |
| `frontend-v2/src/api/catalogApi.js` | API module (UI-4). |
| `frontend-v2/src/pages/__tests__/DiscoverPage.test.jsx` | TST-8. |

### Frontend — modified

| File | Change |
|---|---|
| `frontend-v2/src/App.jsx` | `/discover` route (UI-1). |
| `frontend-v2/src/components/Sidebar.jsx` | "Discover" nav entry (UI-2). |
| `frontend-v2/src/components/NavDrawer.jsx` | Same, if it holds its own list. |
| `frontend-v2/src/components/AttributionLine.jsx` | `from_library` branch (UI-10, FC-4). |
| `frontend-v2/src/pages/RecipesPage.jsx` | Starter-pack removal and empty-state CTA (RM-4 … RM-7). |
| `frontend-v2/src/tutorial/steps.js` | Only if RM-5 requires it. |
| `frontend-v2/src/components/index.js` | Drop the `StarterRecipesModal` export if present. |

### Frontend — deleted

`constants/starterRecipes.js` · `components/StarterRecipesModal.jsx` ·
`constants/__tests__/starterRecipes.test.js` · `components/__tests__/StarterRecipesModal.test.jsx`

### Must not be modified

`backend/shares.py` · `backend/share_routes.py` · `backend/public_pages.py` ·
`backend/public_schema.py` · `backend/public_markup.py` · `backend/public_copy.py` ·
`backend/mealplanner/planner.py` · `backend/mealplanner/scoring.py` · any `/plan` route.

---

## 20. Decisions and rejected alternatives

Recorded so the plan author does not re-open settled questions.

| Decision | Rejected alternative and why |
|---|---|
| System recipes owned by a dedicated `User` row | `user_id = NULL` — collides with `scoping.owned()`, where `None` already means "no scoping", and leaves attribution with nobody to name. A separate `catalog_recipes` table — duplicates the whole recipe shape and forces a second copy path, then a third for user-published recipes. |
| Curation in `catalog_entries`, separate from ownership | Ownership as the catalog test (`user_id == system`) — no home for retirement, and it would have to be retrofitted when users publish. |
| Admin role + admin UI for curation | JSON fixture + sync script — catalog stays in git and survives the unbacked-up alpha database, but every change needs a commit and a script run. Mitigated instead by the export (§9.1). Logging in as the system account — puts a loginable high-value account on production. |
| `is_admin` granted by SQL only | Env-var bootstrap — anyone who can set service variables becomes admin. Admin-grants-admin — a privileged write endpoint guarding a one-person alpha. |
| Popularity derived from `source_recipe_id` | A `catalog_adoptions` table — a second source of truth that drifts from the copies it describes. `copy_count` — never decrements, counts copies not users. |
| `minutes` and `blurb` dropped | Columns on `catalog_entries` — the detail view (UI-7) shows the real recipe, which is better information. Columns on `Recipe` — drags in the model, migration, form, card, import/export and the seed script for a field the app does not use. |
| Attribution reads "From the recipe library" | No attribution at all — the user loses track of where a recipe came from. The system handle as author — makes a fake account look like a person. |
| Own page at `/discover` | A tab on `RecipesPage` — two ownership models, two sets of actions, two sorts and two empty states in the largest page in the app. A modal — a poor home for browsing 60+ recipes with filters and a detail view. |
| Starter modal deleted, empty state routes to `/discover` | Keeping the modal fed by the API — two code paths that add catalog recipes, which will drift. |
| Retire, never delete | Hard delete — loses the adoption count and any record the recipe was offered. Marking adopted copies "retired from library" — implies the user's recipe is deprecated when nothing about it changed. |
| Adoption copies the recipe only, not its sides | Reusing `copy_recipe()`'s two-pass behaviour — adopting one main could silently create two recipes. |
| Population from the ported 60-recipe pack | Mining the live database for the most-held recipes — not reproducible on a fresh database, so CI, `docker compose`, and every new deploy would still need a second population path. |
| Catalog recipes stay `visibility = 'private'` | `'unlisted'` — already means "reachable by a share-token holder". `'public'` — that is Part 2, with its moderation obligations. |

---

## 21. Definition of done

- [ ] Every **MUST** above is implemented or explicitly waived in writing.
- [ ] `pytest` passes from `backend/` (with `mp_test_pg` running).
- [ ] `flake8 .` passes from `backend/`.
- [ ] `npm run test` and `npm run lint` pass from `frontend-v2/`.
- [ ] `tests/test_migrations.py` passes — no model/migration drift.
- [ ] `ALLOW_DESTRUCTIVE_SEED=1 python scripts/seed_testing_data.py` produces a coherent database with a populated catalog, a retired entry, varied adoption counts, and one admin account.
- [ ] `docker compose up` reaches a working app with a populated catalog on a fresh volume.
- [ ] A fresh database reaches 60 published catalog entries through `_bootstrap` alone.
- [ ] No reference to `starterRecipes` or `StarterRecipesModal` remains anywhere in the repository.
- [ ] The `/simplify` skill has been run as the final step, per CLAUDE.md.
