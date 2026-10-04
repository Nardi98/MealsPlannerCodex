# Feedback system — implementation plan

Source design: [2026-09-30-feedback-system-design.md](docs/superpowers/specs/2026-09-30-feedback-system-design.md)
(approved). Branch: `feature/feedback-system`.

## Context

Alpha feedback currently arrives by word of mouth: uncounted, unsearchable, and lost when the
conversation ends. This builds the two halves that replace it — **capture** (a modal reachable from
every page via the profile menu) and **triage** (one admin screen to read, tag, prioritise and close
what arrives). Nothing user-facing reads feedback back; submitting is fire-and-forget and returns only
a quotable ref code. Nightly Claude triage is explicitly out of scope, but `admin_notes` exists now so
that it needs no schema change later.

Four decisions taken before planning, which override the design doc where they differ:

1. **`String` + named `CheckConstraint`**, not native PG enums — the house pattern since
   `67f3715acf44`, and Postgres cannot drop enum values.
2. **Everything is named `user_feedback`**, because `feedback` is already taken by the meal-plan
   accept/reject learning signal (`backend/tests/test_feedback.py`,
   [feedbackApi.js](frontend-v2/src/api/feedbackApi.js)). That module is left untouched.
3. **Two-column split pane** for triage, not the list+modal pattern of the other admin pages.
4. **The seed writes a real screenshot** through `storage.save_image`, so the admin screenshot route
   is exercisable in a `docker compose up` environment.

## How this is parallelised

Four waves. Within a wave, agents own disjoint files and run concurrently; between waves they
serialise. Every agent runs `/test-driven-development` — failing test first, per `CLAUDE.md`.

```
Wave 0  ── foundation (solo, blocking)
             │
    ┌────────┼─────────────┬────────────────┐
Wave 1    A1 domain     F1 capture      F2 triage+nav        (3 parallel)
             │
        ┌────┴────┐
Wave 2   A2 user   A3 admin routes                           (2 parallel)
             │
Wave 3  ── integration + /simplify (solo)
```

Wave 0 is deliberately wide: it lands the models, the migration, the seed, the rate-limit constants,
the storage prefix **and empty pre-wired router shells**. Pre-wiring the routers means `main.py` is
touched exactly once, by wave 0, so A2 and A3 never contend over it — the same reason `CLAUDE.md`
gives for the existing routers being pre-wired.

---

## Wave 0 — foundation (one agent, must land before anything else)

### `backend/models.py`

Append after `AlphaInvite`, the last model in the file, following the `AlphaInvite` /
`catalog_import_items` style — module-level value tuples, named CHECKs, `server_default=func.now()`.
Constraints are named explicitly throughout `models.py` for the reason the file documents: an
unnamed constraint has no name in the metadata to match the reflected one against, so autogenerate
reads it as absent and proposes dropping it on every migration.

```python
FEEDBACK_TYPE_VALUES = ("issue", "request", "improvement", "not_working")
FEEDBACK_STATUS_VALUES = ("open", "in_progress", "closed_fixed", "closed_ignored")
FEEDBACK_PRIORITY_VALUES = ("low", "normal", "high")
```

`FeedbackItem` (`feedback_items`) with the columns in the design doc's table, except:

- `type`/`status`/`priority` are `Column(String, nullable=False, server_default=...)` each with a
  named `CheckConstraint` (`ck_feedback_item_type`, `..._status`, `..._priority`).
- `updated_at` is a real column (`server_default=func.now()`, `onupdate=func.now()`). Note this is the
  **first `updated_at` in the schema**; every other table records change as a separate nullable
  timestamp. Justify it in a comment: triage mutates rows repeatedly and "last touched" is the
  natural sort for an inbox.
- `user_id` → `ForeignKey("users.id", ondelete="SET NULL")`, nullable — the item outlives the account.
- `ref_code` unique + indexed, nullable=False.

`FeedbackTag` (`feedback_tags`): `id`, `name` unique+indexed, with a `@validates("name")` normalizer
(trim, lowercase, collapse inner whitespace) mirroring `AlphaInvite._normalize_email`. Put the normalizer itself in `user_feedback.py` and import it, or keep it local —
either is fine, but one definition only.

`feedback_item_tags`: a bare `Table()` like `recipe_favorite_side_table` (`models.py:287-300`), with
`ondelete="CASCADE"` on **both** columns — not the older `recipe_tag_table` which omits them.

**Tenancy: feedback is deliberately not owner-scoped.** `CLAUDE.md`'s rule is that every per-user row
is owned and every query scoped through `scoping.py`, and a query added without `scope()` leaks one
user's data to another. Feedback is the exception by design, and the exception has to be written down
rather than merely implemented: `user_id` here is *provenance*, not tenancy — it records who filed the
item, which is why it is nullable and `SET NULL` — and the only reader is an admin who must see
everyone's rows. So `FeedbackItem` does **not** use `models._owner_fk_column()` and
`user_feedback.list_items` does **not** call `scope()`. Put that in a comment on the column, or the
next person grepping for unscoped queries will read it as the leak. (The guard
`test_production_calls_to_user_scoped_functions_pass_user_id` constrains only `crud.py`-style
`user_id` parameters, so nothing here trips it.)

### `backend/migrations/versions/<new>_user_feedback.py`

`down_revision = 'c71bc3b77870'` (current head, `alpha_invites`). Three tables + indexes. Model the
script on [c71bc3b77870_alpha_invites.py](backend/migrations/versions/c71bc3b77870_alpha_invites.py)
for shape and `a60c6f33d41f_catalog_import_staging.py` for `CheckConstraint` + mixed-ondelete FKs.
Autogenerate, then **read the script** — autogenerate does not compare CHECK expressions.
`downgrade()` reverses every step.

### `backend/storage.py`

`_key_for` (`storage.py:55-59`) hardcodes the `recipes/` prefix. Add an optional
`prefix: str = "recipes"` parameter threaded through `save_image(data, content_type, prefix="recipes")`
so feedback screenshots land under `feedback/`. Existing callers are unchanged; add a test in
`tests/test_storage.py` that a custom prefix round-trips through `open_image`.

### `backend/ratelimit.py`

Two constants with explanatory comments, added to `__all__` (`ratelimit.py:28-36`):

```python
FEEDBACK_RATE_LIMIT = os.environ.get("FEEDBACK_RATE_LIMIT", "10/hour")
FEEDBACK_ADMIN_RATE_LIMIT = os.environ.get("FEEDBACK_ADMIN_RATE_LIMIT", "240/hour")
```

### Pre-wired router shells

Create `backend/user_feedback_routes.py` and `backend/user_feedback_admin_routes.py` containing only
the module docstring and the `APIRouter(...)` declaration — no routes yet:

```python
router = APIRouter(prefix="/admin/feedback", tags=["feedback-admin"],
                   dependencies=[Depends(auth_users.require_admin)])
```

(copy [alpha_routes.py:32-39](backend/alpha_routes.py#L32-L39) verbatim in shape). Wire both with
`include_router` in the block at [main.py:108-115](backend/main.py#L108-L115) and add the alphabetical
imports at `main.py:29-50`.

### `backend/scripts/seed_testing_data.py`

Per the mandate at `CLAUDE.md:110`. Add the three models to the import list at `:45-58`; a
`FEEDBACK_TAGS` tuple and a `FEEDBACK_ITEMS` spec list near the other data constants; a
`link_user_feedback(session, users)` builder called from `populate` after the ALPHA-GATE block
(`:1015-1026`); and a feedback count in the summary line of `main()` (`:1031-1048`). Spread the rows
across all four types, all four statuses, all three priorities, a mix of `seen`, a couple with
`page_path`/`viewport_width` set, and **one carrying a screenshot** — embed a 1×1 PNG as a bytes
literal and call `storage.save_image(png, "image/png", prefix="feedback")`.

### `backend/tests/test_architecture_guards.py`

Add `"user_feedback.py"` to the parametrize list at `:70`. Also add the containment pair modelled on
`:98-126`: only `main` and its two routers import `user_feedback`, and `user_feedback` imports nothing
of ours but `models` and `storage`.

### Wave 0 verification

```
docker start mp_test_pg
cd backend && python -m pytest tests/test_migrations.py tests/test_architecture_guards.py \
    tests/test_storage.py tests/test_app_wiring.py tests/test_ratelimit.py tests/test_seed.py
python -m flake8 .
alembic upgrade head             # the app never calls create_all; nothing else applies the revision
ALLOW_DESTRUCTIVE_SEED=1 python scripts/seed_testing_data.py
```

`pytest` forces `DATABASE_URL` to `TEST_DATABASE_URL` and drops and rebuilds the schema per run, so
the container above must be the throwaway one. And note that `alembic upgrade head` is wired as the
Railway `api` service's pre-deploy command **in the dashboard, recorded in no file in this repo** —
the app itself never calls `create_all`, so applying the new revision anywhere else, locally
included, is a manual step.

---

## Wave 1 — three agents in parallel

### A1 — `backend/user_feedback.py` + `tests/test_user_feedback_service.py`

A pure domain module in the shape of [alpha.py](backend/alpha.py): imports only `models` and
`storage`, functions take `session: Session` first and commit themselves, "not found" is its own
`LookupError` subclass (`FeedbackItemNotFound`, `FeedbackTagNotFound`) for the routers to translate.

Exactly the signatures in the design doc (`submit`, `list_items`, `get_item`, `mark_seen`,
`set_status`, `set_priority`, `set_notes`, `set_tags`, `list_tags`, `rename_tag`, `unseen_count`).

Points to get right, each a test first:

- `ref_code` is `f"FB-{item.id}"`, written in the **same transaction** as the insert — flush for the
  id, set it, commit.
- `submit` calls `storage.save_image(..., prefix="feedback")` **before** adding the row, so a
  `ValueError` from an unsupported content type leaves no row behind.
- `set_tags` creates missing tags; `Mobile`, `mobile ` and `mobile` are one tag (normalization).
- `list_items` is newest-first and filters compose (`status`, `type`, `priority`, `tag`, `seen`).
- `status` and `seen` are independent: `set_status(..., "closed_fixed")` does not set `seen`.
- `unseen_count` matches the rows.

Fixtures: `db_session`, `user`, `admin_user` from [conftest.py](backend/tests/conftest.py); point
`storage.MEDIA_DIR` at `tmp_path` and `monkeypatch.delenv("AWS_S3_BUCKET_NAME")` as
`tests/test_recipe_image_upload.py:8-18` does.

### F1 — capture (frontend)

Owns: `src/api/userFeedbackApi.js`, `src/components/FeedbackModal.jsx`,
`src/components/ProfileMenu.jsx`, `src/components/index.js`, and tests. **Does not touch App.jsx or
Sidebar.jsx.**

- `userFeedbackApi.js` modelled on [alphaApi.js](frontend-v2/src/api/alphaApi.js) — named *and*
  default export, rows unnormalised, error copy imported from `catalogApi` (`apiErrorText`,
  `asSentence`) rather than redefined. One call: `submit(fields, file)` building a `FormData` and
  POSTing to `/feedback`. `client.js` already detects `FormData` and drops the JSON content-type
  ([client.js:36-41](frontend-v2/src/api/client.js#L36-L41)) — mirror
  [recipesApi.js:105-110](frontend-v2/src/api/recipesApi.js#L105-L110).
- `FeedbackModal.jsx` on the existing `Modal` (`{title, onClose, children, maxWidth}`), `Input`
  (`as="textarea"` for the body), `SegmentedControl` for the type, `Button`, and a raw
  `<input type="file" accept="image/*">` with the upload states copied from
  [NewRecipeModal.jsx:418-440](frontend-v2/src/components/NewRecipeModal.jsx#L418-L440) — there is no
  file-picker primitive and this plan does not add one.
- It reads its own context: `useLocation().pathname`, `window.innerWidth`, `navigator.userAgent`, and
  says in one line that the current page is included.
- On success it shows the ref code, then closes.
- `ProfileMenu.jsx`: one more `useState`, one more row between Preferences and Log out reusing
  `menuItemStyle` (`:112-122`) and the `setOpen(false); setShowX(true)` pattern at `:80-83`, and the
  modal rendered as a sibling of the dropdown at `:105-107`.
- Tests (`src/components/__tests__/FeedbackModal.test.jsx`, and extend
  `ProfileMenu.test.jsx`): follows the per-file convention — `/** @vitest-environment jsdom */`,
  explicit `import '@testing-library/jest-dom/vitest'`, own `afterEach(cleanup)`; mock the api module
  with a factory as [ShareRecipeModal.test.jsx:11-13](frontend-v2/src/components/__tests__/ShareRecipeModal.test.jsx#L11-L13)
  does. Assert: empty title blocks submit; the captured `page_path` is sent; the returned ref code is
  shown. **Note** `ProfileMenu.test.jsx` does not mock its child modals, so `FeedbackModal` must not
  fetch on mount.

### F2 — triage + nav (frontend)

Owns: `src/api/userFeedbackAdminApi.js`, `src/pages/FeedbackAdminPage.jsx`, `src/App.jsx`,
`src/components/Sidebar.jsx`, `src/components/NavDrawer.jsx`, and their tests. **Does not touch
ProfileMenu.jsx.**

- Route: `<Route path="/discover/feedback" element={<AdminOnlyRoute><FeedbackAdminPage /></AdminOnlyRoute>} />`
  in the admin block at [App.jsx:190-204](frontend-v2/src/App.jsx#L190-L204), beside the ALPHA-GATE
  line.
- Nav entry in `NAV` ([Sidebar.jsx:25-43](frontend-v2/src/components/Sidebar.jsx#L25-L43)) exactly as
  the design doc writes it, with `ChatBubbleLeftEllipsisIcon` from `@heroicons/react/24/outline` and
  `color: 'var(--cat-berry)'`. Berry is also Recipes' colour, but Recipes is `USER_ONLY` so the two
  are never rendered together — write that justification as a comment, which the file's style demands.
- **Unseen badge.** Sidebar has no badge mechanism today and is rendered twice (desktop
  `App.jsx:174` and inside `NavDrawer`), so fetching inside it would double-fetch on mobile. Fetch
  the count once in the `Shell`/`App` layer (only when `isAdminMode`), pass it as a
  `badges={{ '/discover/feedback': n }}` prop to both `Sidebar` instances, and render it as a
  right-aligned inline pill — **not** the `Badge` primitive, which is tuned for light surfaces while
  the sidebar is `surface-dark`. Give the pill an `aria-label` ("3 unread") and update the two
  exhaustive `textContent` assertions in
  [Sidebar.test.jsx:54-59](frontend-v2/src/components/__tests__/Sidebar.test.jsx#L54-L59), as was done
  for Alpha.
- `FeedbackAdminPage.jsx` — **two-column split pane**: rows left, persistent detail right, collapsing
  to list-then-detail under the mobile breakpoint (`src/test/stubViewport.js` shows how viewport is
  stubbed in tests). This is a new layout for this codebase, so build it from the pieces that exist
  rather than inventing chrome: the row list is a `Card style={{padding:0}}` wrapping a
  `<ul aria-labelledby>` of `<li>`s separated by `borderTop`, as
  [AlphaPage.jsx:234-241](frontend-v2/src/pages/AlphaPage.jsx#L234-L241); the filter bar follows
  [CatalogAdminToolbar.jsx:26-70](frontend-v2/src/components/catalog/CatalogAdminToolbar.jsx#L26-L70)
  (`role="group"`, `Input as="select"`), with `useDebounced` if a text filter is added.
- Reuse, do not re-write: `CatalogLoadFailed` (`{message, onRetry}`), `CatalogNoticeBar`
  (`{notice, onDismiss}` where `notice.kind` doubles as the ARIA role), `textStyles.js`
  (`mutedTextStyle`, `sectionHeadingStyle`), `Badge` for the type/status chips, `ConfirmModal`.
- State shape copied from `AlphaPage` (`:53-59`): `rows = null` until first load, `failed`,
  `reloadKey`, `notice`, `busy`, plus `selectedId`; one `run(what, body)` mutation wrapper (`:94-106`).
- Opening a row marks it seen (`PATCH {seen: true}`) and decrements the badge.
- Tests (`src/pages/__tests__/FeedbackAdminPage.test.jsx`): mock the api module with
  `importOriginal` spread as [AlphaPage.test.jsx:19-23](frontend-v2/src/pages/__tests__/AlphaPage.test.jsx#L19-L23),
  `stubViewport(false)`, `globalThis.fetch` rejecting. Assert: filters by status and by tag; opening a
  row marks it seen; Sidebar shows Feedback in admin mode and not in user mode.

---

## Wave 2 — two agents in parallel (after A1)

Both edit only their own router file; `main.py` was wired in wave 0. Pydantic models are **local to
each router**, with `model_config = ConfigDict(extra="forbid")`, per
[alpha_routes.py:42-84](backend/alpha_routes.py#L42-L84).

### A2 — `backend/user_feedback_routes.py` + `tests/test_user_feedback_routes.py`

`POST /feedback`, multipart (fields plus an optional image part), `current_user: CurrentUser`.
Rate limited: `@ratelimit.limiter.limit(ratelimit.FEEDBACK_RATE_LIMIT)` **below** the route decorator,
and the handler **must** take `request: Request` first — slowapi reads the key off the request
(`ratelimit.py:14-15`). Enforce `_MAX_IMAGE_BYTES` as `main.py:921` does (413 over the cap).

`storage.ValueError` → 400 **and no row written** (the design doc says 400 here; recipe upload returns
415 — keep the doc's 400 and note the divergence in a comment). Response body is exactly
`{"ref_code": "FB-104"}`. There is no list or read route for users, their own included.

Tests: happy path; missing title or body rejected; unknown `type` rejected; `ref_code` is `FB-<id>`;
`page_path`/`user_agent`/`viewport_width` stored; image stored and readable back; non-image content
type is 400 with no row; the n+1-th call in the window is 429 (re-enable the limiter with
`monkeypatch.setattr(app.state.share_limiter, "enabled", True)` and a real bearer token, as
[test_catalog_admin.py:763-791](backend/tests/test_catalog_admin.py#L763-L791) does — the limiter reads
the header, not the dependency override). Multipart calls follow
[test_recipe_image_upload.py](backend/tests/test_recipe_image_upload.py).

### A3 — `backend/user_feedback_admin_routes.py` + `tests/test_user_feedback_admin.py`

The seven routes of the design doc's table. `require_admin` stays a **router-level** dependency (wave
0 set it) so a forgotten `Depends` cannot happen. Writes carry
`@ratelimit.limiter.limit(ratelimit.FEEDBACK_ADMIN_RATE_LIMIT)`; reads are undecorated and take no
`request`, exactly as `catalog_admin_routes` splits them.

`PATCH /admin/feedback/{id}` takes `status`, `priority`, `admin_notes`, `tags`, `seen` — each
optional, dispatching to the matching `user_feedback` setter. `GET /admin/feedback/{id}/screenshot`
streams via `storage.open_image`; `FileNotFoundError` → 404.

**Route ordering matters:** `/admin/feedback/tags` must be declared before `/admin/feedback/{id}` or
FastAPI will try to parse `tags` as an id.

Tests, mirroring [test_catalog_admin.py:62-191](backend/tests/test_catalog_admin.py#L62-L191):

- a frozen `CONTRACT_ROUTES` set and `_router_table()`, asserting the router serves exactly those;
- `require_admin` is in `router.dependencies`;
- a parametrized sweep over every `(method, path)`: 401 anonymous, and **one byte-identical 403** for
  a signed-in non-admin whether the id exists or not (`MISSING_ID = 10**9`) — the screenshot stream
  included;
- `admin_notes` and `screenshot_key` appear in no user-facing response;
- tags: inline creation, case/padding reuse, rename, filtering by tag;
- `unseen-count` matches the rows.

Add a `test_the_feedback_routers_are_included` to `tests/test_app_wiring.py` alongside the
catalog-admin assertion at `:41-49`.

---

## Wave 3 — integration (solo)

1. Full suites, both sides:
   ```
   docker start mp_test_pg
   cd backend && python -m flake8 . && python -m pytest
   cd ../frontend-v2 && npm run lint && npm run test && npm run build
   ```
2. End-to-end by hand: `docker compose up` (which reseeds), sign in as the demo admin, open the
   profile menu → **Send feedback**, submit with a screenshot, confirm the ref code; switch to admin
   mode, open **Feedback**, confirm the badge count, open the row (badge decrements), view the
   screenshot, set a status and priority, type a new tag, filter by it, write a note; then sign in as
   a non-admin and confirm `/discover/feedback` redirects and `/admin/feedback` returns 403.
3. Update `CLAUDE.md`:
   - the backend-layers paragraph currently reads "**eight** routers are pre-wired with
     `include_router` (`main.py:108-115`)" and enumerates them — make it **ten**, add
     `user_feedback_routes.py` and `user_feedback_admin_routes.py`, and re-check the cited line
     range, which wave 0 will have shifted;
   - a `user_feedback.py` bullet in the same section, shaped like the `catalog.py` and `alpha.py`
     bullets: what it owns, and that it imports only `models` and `storage`, guarded by
     `tests/test_architecture_guards.py`;
   - the **Auth & tenancy** section — one sentence recording feedback as the deliberate *unscoped*
     exception, next to the existing note that `ops_routes.py` is the deliberate *unauthenticated*
     one;
   - the frontend `pages/` list, with `FeedbackAdminPage` at `/discover/feedback`.
4. Run `/simplify` on the branch, as `CLAUDE.md` requires as the last step of every plan.

## Risks worth naming

- **`updated_at` is new to this schema.** `test_migrations.py` compares types exactly, so the
  `server_default`/`onupdate` pair must be expressed identically in model and migration.
- **The split pane is new UI.** It is the one place this plan has no precedent to copy; if F2 finds
  itself inventing chrome, falling back to list+detail-modal is a legitimate retreat — say so rather
  than building a half-pane.
- **Berry collides across modes.** Defensible (Recipes is user-only) but it is a judgement the
  Sidebar comments oblige us to write down.
- **Every `file:line` here is a snapshot.** `models.py`, `main.py` and `CLAUDE.md` have all moved
  since the design doc was written — the documented router count alone went from seven to eight.
  Treat each reference as a pointer to a *pattern* and re-locate it before editing.
- **The old `feedback` feature.** Nothing in this plan touches `api/feedbackApi.js`,
  `tests/test_feedback.py`, or the accept/reject routes in `main.py`. A reviewer seeing both names
  should find the new ones consistently prefixed `user_feedback` / `userFeedback`.
