# Alpha email allowlist — Implementation Plan

**Spec:** `docs/superpowers/specs/2026-09-30-alpha-allowlist-design.md` (approved, binding — do not redesign).
**Plan file to commit:** `docs/superpowers/plans/2026-09-30-alpha-allowlist.md`
**Integration branch:** `feature/alpha-allowlist`. No push, no PR unless asked.

## Context

The closed alpha must be invitation-only: only addresses the admin has listed may create an account. Today `POST /auth/register` ([main.py:460-524](backend/main.py#L460-L524)) and `POST /auth/google`'s account-creation branch ([main.py:599-615](backend/main.py#L599-L615)) accept any address. The admin has no screen to manage an allowlist.

This is temporary scaffolding: when the alpha ends the whole feature is deleted. So the governing constraint is **removability** — every artefact carries the grep-able `ALPHA-GATE` marker, and all dependency arrows point *into* the feature. Exactly three marked lines in `main.py`, one route line in `App.jsx`, one `Sidebar.jsx` NAV entry, one seed block.

Everything reuses existing machinery: `auth_users.require_admin` ([auth_users.py:214-226](backend/auth_users.py#L214-L226)), `models.normalize_email` ([models.py:165-173](backend/models.py#L165-L173)), the local-Pydantic router convention of [catalog_admin_routes.py:74-78](backend/catalog_admin_routes.py#L74-L78), `AdminOnlyRoute` ([App.jsx:81-83](frontend-v2/src/App.jsx#L81-L83)), the `components/catalog/` primitives, and `api/client.js`'s `request()`.

Outcome: a signup gate that fails open on an empty table, four admin routes, and one admin page — all removable in three steps.

## Decisions (binding — do not re-open)

| # | Decision |
|---|---|
| D1 | **One git worktree per agent**, each on its own task sub-branch with its own Postgres DB `mealsdb_test_<task>`. The orchestrator merges each branch into `feature/alpha-allowlist`. |
| D2 | Shared files have exactly **one** owner (collision map below). An agent needing a change outside its owned list **stops and reports**. |
| D3 | `alpha.py` reuses `models.normalize_email` rather than re-deriving `strip().lower()` — one canonicalisation rule in the codebase. |
| D4 | `alpha.py` may import `pydantic` (`TypeAdapter(EmailStr)`) beyond the spec's literal import list. The spec's list is about *repo* coupling; per-token validation cannot live in a Pydantic field because an invalid address must be **reported, not fatal**. |
| D5 | The POST body is one free-text `str` field named `emails`; validation and partitioning happen in the service. |
| D6 | Every implementing agent MUST invoke the `/test-driven-development` skill and work red → green → refactor (CLAUDE.md). |
| D7 | Order of the final wave: full automated verification → **`/simplify`** → **manual UI pass** last. One user-testing pause, at the end. |
| D8 | Model + Alembic revision + seed update land in **one commit** (CLAUDE.md), which is why A1 owns all three. |
| D9 | Seed invites: the three seeded account emails **plus** one not-yet-signed-up address, so the admin table shows both `Signed up` and `Invited` badges out of the box. |
| D10 | Only **A1** runs `tests/test_migrations.py` (it uses a fixed scratch DB name `mealsdb_migrations`). Everyone else passes `--ignore=tests/test_migrations.py`. |

## Execution model

### Orchestrator (main session)
1. Commit this plan to `docs/superpowers/plans/2026-09-30-alpha-allowlist.md` on `feature/alpha-allowlist` **before dispatching anything**, so every worktree contains it.
2. Dispatch with `Agent` (`subagent_type: "general-purpose"`, `isolation: "worktree"`, `run_in_background: true`). Start a task as soon as its deps are **merged**.
3. On a report: read it, `git merge --no-ff <task-branch>`, then the **merge gate** — from `backend/`: `python -m pytest --ignore=tests/test_migrations.py`; `python -m flake8 .`; and if frontend files changed, from `frontend-v2/`: `npm run test`; `npm run lint`.
4. Dispatch newly unblocked tasks from the new HEAD.

### Agent prompt template
> You are implementing **Task \<id\>** of `docs/superpowers/plans/2026-09-30-alpha-allowlist.md` in your own git worktree. Read the plan's "Execution model", "Contracts (frozen)" and your task section, plus the spec. Invoke the `/test-driven-development` skill and follow it: write each listed test first, watch it fail, then implement. Edit **only** the files your task owns; if you need a change elsewhere, stop and report it. Every new file and every edited line in an existing file carries an `ALPHA-GATE` comment. Use your own test database as described under "Per-agent environment". Commit on your worktree branch with focused commits ending in `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`. Do not push. Finish with a report: branch, files changed, verification commands run with pass/fail output, and any deviation or open question.

### Per-agent environment (PowerShell — shell state does not persist, so set env vars in the same command)
Backend, from `<worktree>/backend`:
```powershell
docker start mp_test_pg
docker exec mp_test_pg psql -U user -d postgres -c "CREATE DATABASE mealsdb_test_a1;"
$env:TEST_DATABASE_URL='postgresql://user:pass@localhost:5432/mealsdb_test_a1'; python -m pytest --ignore=tests/test_migrations.py
python -m flake8 .
```
(substitute `a1`/`a2`; flake8 max line length 120.) Frontend, from `<worktree>/frontend-v2`: `npm ci` once, then `npm run test` and `npm run lint`.

---

## Contracts (FROZEN — parallel tasks build against these and do not negotiate)

### `backend/alpha.py` — symbol table (owner A1)

Module docstring opens with `ALPHA-GATE`. Imports: `sqlalchemy` / `sqlalchemy.orm.Session`, `models`, `fastapi.HTTPException`, `pydantic`. Nothing else. Imported by `alpha_routes.py` and the marked `main.py` lines only.

| Symbol | Behaviour |
|---|---|
| `NOT_INVITED_DETAIL: str` | Exactly `"Meal Planner is in a closed alpha. This email address hasn't been invited yet."` (ASCII apostrophe). |
| `normalize(email) -> str` | `models.normalize_email(email)`. Applied on every write and every lookup. |
| `is_valid_email(value) -> bool` | Module-level `pydantic.TypeAdapter(EmailStr)`; returns bool, never raises. |
| `split_emails(raw) -> list[str]` | Splits on newlines **and** commas, strips, drops empties, de-duplicates **by normalised form** preserving first-seen order, returns tokens as typed (so `invalid` echoes what was pasted). |
| `InviteNotFound(LookupError)` | Raised by `update_note` / `delete_invite`. |
| `InviteRow(NamedTuple)` | `invite`, `signed_up: bool`, `signed_up_at: datetime \| None`. |
| `AddResult(NamedTuple)` | `added`, `skipped_duplicates` (both normalised), `invalid` (raw). |
| `assert_email_allowed(session, email) -> None` | 1. `SELECT EXISTS(SELECT 1 FROM alpha_invites)` → no rows: **return** (fail open). 2. normalised match → return. 3. else `raise HTTPException(403, NOT_INVITED_DETAIL)`. Never writes, never commits. |
| `list_invites(session) -> list[InviteRow]` | All rows, `created_at DESC, id DESC`. `signed_up`/`signed_up_at` derive from an OUTER JOIN `users ON users.email = alpha_invites.email` — one query, no denormalised state. |
| `add_invites(session, raw, *, invited_by_user_id) -> AddResult` | `split_emails` → invalid tokens to `invalid`; already in table (one `IN` query, not per token) or already added in this batch → `skipped_duplicates`; else insert → `added`. **Exactly one `commit()`**, rollback on exception. |
| `update_note(session, invite_id, note)` | Note only, never the email. Stripped; empty → `None`. Commits. `InviteNotFound` if absent. |
| `delete_invite(session, invite_id) -> None` | Commits. `InviteNotFound` if absent. |

### `backend/models.py` — new model (owner A1)

```python
# ALPHA-GATE: the closed-alpha signup allowlist. Deleted whole when the alpha
# ends (docs/superpowers/specs/2026-09-30-alpha-allowlist-design.md).
class AlphaInvite(Base):
    """One email address permitted to create an account during the closed alpha."""

    __tablename__ = "alpha_invites"

    id = Column(Integer, primary_key=True, index=True)
    # Stored normalized, so the stored value is the only form that exists.
    email = Column(String, nullable=False, unique=True, index=True)
    note = Column(String, nullable=True)
    # Null once the admin who added the row is gone: the invite outlives them.
    invited_by_user_id = Column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    @validates("email")
    def _normalize_email(self, _key, value):
        return normalize_email(value)
```
**No relationship is declared on `User`** — the arrow points one way, so nothing in `User` mentions the alpha.

### `backend/migrations/versions/<rev>_alpha_invites.py` (owner A1)
`down_revision = 'a60c6f33d41f'` (current head, `catalog_import_staging`). Typed `revision: str` / `down_revision: Union[str, Sequence[str], None]`; docstrings `"""Upgrade schema."""` / `"""Downgrade schema."""`; creates the table with `server_default=sa.text('now()')`, the unique constraint and `ix_alpha_invites_email`; `downgrade()` drops index then table. No data migration.

### HTTP — `backend/alpha_routes.py` (owner A2)
`router = APIRouter(prefix="/admin/alpha", tags=["alpha"], dependencies=[Depends(auth_users.require_admin)])`. Local Pydantic models, all `model_config = ConfigDict(extra="forbid")`. Nothing added to `schemas.py`.

```
InviteOut = { id, email, note: str|null, created_at, signed_up: bool, signed_up_at: datetime|null }

GET    /admin/alpha/invites              -> 200 [InviteOut]            # newest first
POST   /admin/alpha/invites   {"emails": str}    # newline/comma separated free text
                                         -> 200 {"added":[], "skipped_duplicates":[], "invalid":[]}
PATCH  /admin/alpha/invites/{id} {"note": str|null}
                                         -> 200 InviteOut | 404 {"detail":"Invite not found"}
DELETE /admin/alpha/invites/{id}         -> 204 no body | 404 {"detail":"Invite not found"}
```
Every route: anonymous → **401** `{"detail":"Not authenticated"}`; non-admin → **403** `{"detail":"Forbidden"}`, byte-identical whether the id exists or not. Response bodies from an explicit field allowlist, never the ORM object — `invited_by_user_id` is **not** exposed. `{"emails": ""}` is valid → three empty lists. No rate limiting (admin-only, four routes, temporary). The POST handler takes `current_user` for `invited_by_user_id`.

### Gate call sites — `backend/main.py` (owner A2)
```python
app.include_router(alpha_routes.router)   # ALPHA-GATE
```
In `register`, **before** `existing = crud.get_user_by_email(...)` (~line 480) — this ordering preserves the endpoint's deliberate anti-enumeration property:
```python
alpha.assert_email_allowed(db, payload.email)  # ALPHA-GATE: closed-alpha allowlist
```
In `login_with_google`, inside `if user is None:` **after** the `email_verified` check and **before** `_create_account`, the same call with `email`. No other endpoint is touched.

### `backend/scripts/seed_testing_data.py` (owner A1) — D9
Inside `populate(session)`, before the single final commit: `AlphaInvite` rows for `DEMO_USER_EMAIL`, `FRIEND_USER_EMAIL`, `GUEST_USER_EMAIL` (`invited_by_user_id` = demo user, notes naming each role) plus `alpha-pending@mealplanner.test`, note `"invited, has not signed up yet"`. Block carries `# ALPHA-GATE`.

### `frontend-v2/src/api/alphaApi.js` (owner F1)
```js
import { request } from './client';

const BASE = '/admin/alpha/invites';
const json = (method, body) => ({ method, body: JSON.stringify(body) });

export const alphaApi = {
  list: () => request(BASE),
  add: (emails) => request(BASE, json('POST', { emails })),
  updateNote: (id, note) => request(`${BASE}/${encodeURIComponent(id)}`, json('PATCH', { note })),
  remove: (id) => request(`${BASE}/${encodeURIComponent(id)}`, { method: 'DELETE' }),
};

export default alphaApi;
```
Rows pass through unnormalised (the `catalogApi` precedent). `apiErrorText` / `asSentence` are **imported from `catalogApi`**, never duplicated. Header carries `// ALPHA-GATE`.

### Frontend routing (owner F2)
- `App.jsx`: `<Route path="/discover/alpha" element={<AdminOnlyRoute><AlphaPage /></AdminOnlyRoute>} />` after `/discover/import/:batchId` (line ~201), with `{/* ALPHA-GATE */}`.
- `Sidebar.jsx`, **after** the Import entry (line ~33): `{ label: 'Alpha', path: '/discover/alpha', Icon: EnvelopeIcon, color: '<unused category token>', modes: ADMIN_ONLY, match: (p) => p === '/discover/alpha' }` with `// ALPHA-GATE`. Taken hues: berry, terracotta, sky, plum, olive, teal, `--c-a2`. F2 picks a remaining token from `MEAL_PLANNER_DESIGN_GUIDE.md` and records the choice in its report.

---

## Dependency graph & waves

```
WAVE 1 (2 agents in parallel)
  A1  models.AlphaInvite + migration + seed + alpha.py + unit tests    [backend]
  F1  api/alphaApi.js + its test                                       [frontend]

WAVE 2 (2 agents in parallel, each after its dep)
  A2  alpha_routes.py + main.py wiring & both guards + arch guard      [backend]   deps: A1
  F2  AlphaPage.jsx + App.jsx route + Sidebar.jsx row + tests          [frontend]  deps: F1

WAVE 3 (sequential, orchestrator)
  I1  automated integration verification
  S1  /simplify + docs sweep
  P1  manual UI pass  ═ PAUSE (user testing)
```
Peak concurrency 2, deliberately shallow: A2 cannot precede A1 (route tests need the table), and F2 mocks `alphaApi` via `importOriginal()`, which needs the real module on disk.

### Shared-file rule (collision map)

| Shared file | Sole owner | When | Note |
|---|---|---|---|
| `backend/main.py` | **A2** | Wave 2 | All three marked lines in one task — splitting router-wiring from the guards puts two agents in one file *and* leaves A2's route tests unmountable. |
| `backend/models.py` | **A1** | Wave 1 | Append-only, one class. |
| `backend/scripts/seed_testing_data.py` | **A1** | Wave 1 | Same commit as model + migration (D8). |
| `backend/tests/test_architecture_guards.py` | **A2** | Wave 2 | Extends the existing parametrize + one reverse-direction test. |
| `backend/tests/conftest.py` | **nobody** | — | Existing `db_session` / `user` / `admin_user` / `db_client` / `client_as` suffice; task-local fixtures live in the task's own test module. |
| `backend/schemas.py` | **nobody** | — | Spec forbids touching it. |
| `frontend-v2/src/api/alphaApi.js` | **F1** | Wave 1 | F2 consumes, never edits. |
| `frontend-v2/src/api/catalogApi.js` | **nobody** | — | F1/F2 import from it; no edit. |
| `frontend-v2/src/App.jsx` | **F2** | Wave 2 | One import + one route line. |
| `frontend-v2/src/components/Sidebar.jsx` | **F2** | Wave 2 | One icon import + one NAV entry. |

`tests/test_migrations.py` is run by **A1 only** and by the orchestrator in I1 — never two at once (D10).

---

## WAVE 1

### A1 — Table, migration, seed, service `[backend]` — deps: none
**Owns:** `backend/models.py`, `backend/migrations/versions/<rev>_alpha_invites.py` (new), `backend/alpha.py` (new), `backend/scripts/seed_testing_data.py`, `backend/tests/test_alpha.py` (new). Nothing else.

**Tests first** (fixtures `db_session`, `user`, `admin_user`):
- Model: `"  Mixed@Case.COM "` reads back `mixed@case.com`; a second row with the same normalised email raises `IntegrityError`; `created_at` populates unpassed; `invited_by_user_id` accepts `None`.
- `split_emails`: `"a@x.com, b@x.com\nc@x.com"` → 3 tokens; blank lines / trailing comma / whitespace produce no empties; `"A@x.com\na@x.com"` → one token, the first as typed.
- `is_valid_email`: accepts `a@x.com`; rejects `""`, `"nope"`, `"a@"`, `"a b@x.com"`.
- `assert_email_allowed`:
  - **empty table returns `None`** (fail open) — the headline test, named so.
  - a listed email returns; `"  LISTED@X.COM "` also returns.
  - an unlisted email raises `HTTPException` with `status_code == 403` and `detail == alpha.NOT_INVITED_DETAIL`, plus one assertion against the literal sentence text.
  - nothing is written: the row count is unchanged after a rejection.
- `add_invites`: with `dupe@x.com` present, `"new@x.com, dupe@x.com\nnot-an-email\nNEW@x.com"` → `added == ["new@x.com"]`, `skipped_duplicates == ["dupe@x.com"]`, `invalid == ["not-an-email"]`, exactly one row inserted; stored emails normalised; `invited_by_user_id` set; `""` → three empty lists, no rows, and (spying on `session.commit`) at most one commit.
- `list_invites`: newest first; `signed_up` true with the user's `created_at` as `signed_up_at` when a `User` holds that address (including a case-only difference), else false/None.
- `update_note`: sets it; `"  "` → `None`; the email is unchanged; missing id → `InviteNotFound`.
- `delete_invite`: removes the row; missing id → `InviteNotFound`.
- Seed (modelled on `tests/test_seed_sharing_data.py`): after `populate(session)` the demo/friend/guest addresses each have an invite and at least one invite has no matching user.

**Implement:** the model, then generate and hand-correct the migration:
```powershell
docker exec mp_test_pg psql -U user -d postgres -c "CREATE DATABASE mealsdb_alembic_a1;"
$env:DATABASE_URL='postgresql://user:pass@localhost:5432/mealsdb_alembic_a1'; $env:JWT_SECRET='x'; alembic upgrade head; alembic revision --autogenerate -m "alpha invites"
```
*Read* the generated script. Then `alpha.py` per Contracts, then the seed rows. One commit for model + migration + seed (D8).

**Verify** (from `backend/`) — A1 is the only task running the full suite including migrations:
```powershell
docker start mp_test_pg
docker exec mp_test_pg psql -U user -d postgres -c "CREATE DATABASE mealsdb_test_a1;"
$env:TEST_DATABASE_URL='postgresql://user:pass@localhost:5432/mealsdb_test_a1'; python -m pytest
python -m flake8 .
$env:DATABASE_URL='postgresql://user:pass@localhost:5432/mealsdb_alembic_a1'; $env:JWT_SECRET='x'; $env:ALLOW_DESTRUCTIVE_SEED='1'; python scripts/seed_testing_data.py
```

### F1 — `alphaApi.js` `[frontend]` — deps: none (builds against frozen Contracts)
**Owns:** `frontend-v2/src/api/alphaApi.js`, `frontend-v2/src/api/__tests__/alphaApi.test.js`.
**Must not touch:** `catalogApi.js`, `App.jsx`, `Sidebar.jsx`, any page.

**Tests first** (`vi.mock('../client')`, per the existing api tests):
- `list()` → `request('/admin/alpha/invites')`, no options.
- `add('a@x.com, b@x.com')` → `{ method: 'POST', body: '{"emails":"a@x.com, b@x.com"}' }` — assert the **serialised body**, pinning the field name `emails`.
- `updateNote(7, 'note')` → PATCH `/admin/alpha/invites/7` body `{"note":"note"}`; `updateNote(7, null)` sends `{"note":null}`, so clearing is expressible.
- `remove(7)` → `{ method: 'DELETE' }` on `/admin/alpha/invites/7`.
- An id needing encoding is encoded.
- The module defines no error-text helper of its own (it reuses `catalogApi`'s).

**Verify:** from `frontend-v2/`: `npm run test`, then `npm run lint`.

---

## WAVE 2

### A2 — Router + gate wiring + architecture guard `[backend]` — deps: A1
**Owns:** `backend/alpha_routes.py` (new), `backend/main.py` (**only** `import alpha`, `import alpha_routes`, the `include_router` line, the two guard lines), `backend/tests/test_alpha_routes.py` (new), `backend/tests/test_alpha_gate.py` (new), `backend/tests/test_architecture_guards.py`.
**Must not touch:** `alpha.py`, `models.py`, the migration, the seed — report any service gap instead.

**Tests first — `test_alpha_routes.py`** (template: [test_catalog_admin.py:158-191](backend/tests/test_catalog_admin.py#L158-L191)):
- Build `ROUTER_TABLE` from `alpha_routes.router.routes`; assert it equals the frozen four-pair `CONTRACT_ROUTES` set, so an extra route cannot appear unnoticed.
- Parametrized over it: anonymous → **401**; non-admin → **403** `{"detail":"Forbidden"}`, with the existing-id and `MISSING_ID` responses byte-identical (`.content` and the `content-type` header).
- `any(dep.dependency is auth_users.require_admin for dep in alpha_routes.router.dependencies)`.
- `GET` as admin: newest first; keys exactly `{id, email, note, created_at, signed_up, signed_up_at}`; **no** `invited_by_user_id`, no inviter email/username; `signed_up` true with a timestamp for a seeded user's address, false/null otherwise.
- `POST` partitioning end-to-end: one body with a new address, an already-listed one and `"garbage"` returns the three lists exactly; a second identical POST returns everything as `skipped_duplicates` and adds nothing.
- `POST {"emails": ""}` → 200, three empty lists. `POST {"emails": 1}` → 422. `POST {"emails":"a@x.com","note":"x"}` → 422 (`extra="forbid"`).
- `PATCH` sets the note and returns the row; `{"note": null}` clears it; a body carrying `"email"` → 422; missing id → 404.
- `DELETE` → 204 with an empty body, row gone; missing id → 404; deleting an invite whose account exists leaves the `User` row intact.
- **Marker test:** `main.py` contains exactly three `ALPHA-GATE` lines, and each alpha source file mentions it in its first 20 lines — the removal checklist becomes enforced, not aspirational.

**Tests first — `test_alpha_gate.py`:**
- Empty table: `POST /auth/register` still succeeds (fail open).
- Rows present: uninvited email → 403 with `NOT_INVITED_DETAIL` and **no user row created**; invited email → 201; an address invited in a different case registers fine.
- **Anti-enumeration preserved:** registering an uninvited email that *already has an account* returns the same 403 with the same detail as an uninvited unknown address (the guard precedes the duplicate lookup); an *invited* existing email still returns the neutral 201.
- `POST /auth/google` (mock `auth_users.verify_google_token` as [test_auth_google.py:30](backend/tests/test_auth_google.py#L30) does): new uninvited email → 403, nothing created; new invited email → 200; an **existing** user whose email is not listed signs in successfully (never gated).
- `POST /auth/login` and `/auth/refresh` for an existing unlisted account still succeed (assert both explicitly).

**Tests first — `test_architecture_guards.py`:** extend the existing parametrize to `["catalog.py", "catalog_import.py", "alpha.py"]`; add one test using the existing `_imported_modules` helper asserting that among `_production_modules()` only `main.py` and `alpha_routes.py` import `alpha`, and that `alpha.py` imports none of `main`, `*_routes`, `schemas`, `crud`, `auth_users`.

**Implement:** the router per Contracts (local Pydantic models, `ConfigDict(extra="forbid")`, `Db` / `CurrentUser` aliases declared locally so it never imports `main`). `InviteNotFound` → `HTTPException(404, "Invite not found")`. Then the three `main.py` lines.

**Verify:**
```powershell
docker start mp_test_pg
docker exec mp_test_pg psql -U user -d postgres -c "CREATE DATABASE mealsdb_test_a2;"
$env:TEST_DATABASE_URL='postgresql://user:pass@localhost:5432/mealsdb_test_a2'; python -m pytest --ignore=tests/test_migrations.py
python -m flake8 .
```

### F2 — `AlphaPage` + navigation `[frontend]` — deps: F1
**Owns:** `frontend-v2/src/pages/AlphaPage.jsx`, `frontend-v2/src/pages/__tests__/AlphaPage.test.jsx`, `frontend-v2/src/App.jsx` (one import + one route), `frontend-v2/src/components/Sidebar.jsx` (one icon import + one NAV entry), and `frontend-v2/src/__tests__/App.test.jsx` only if it asserts on NAV or the admin route table.
**Must not touch:** `alphaApi.js`, `catalogApi.js`, `SystemVocabularyPage.jsx`, `CatalogNoticeBar.jsx`.

**Tests first** (per-file `/** @vitest-environment jsdom */`; `vi.mock('../../api/alphaApi', …)` with `importOriginal()`; `globalThis.fetch` stubbed to reject; role/name queries — model on [SystemVocabularyPage.test.jsx](frontend-v2/src/pages/__tests__/SystemVocabularyPage.test.jsx)):
- Header: 3 invites, 2 signed up → shows `3 invited` and `2 signed up`.
- Rows: a signed-up row shows a `Signed up` badge, an unclaimed one shows `Invited`; the added date renders; emails render verbatim.
- **Empty state:** `list` → `[]` renders a warning that there are no invites and **signup is open to everyone** — assert on the words "open to everyone" and on the alert/status role. The fail-open case must be visible, not inferred.
- Add box: two addresses typed, **Add invites** pressed → `alphaApi.add` called with the raw text; a result `{added:['a@x.com'], skipped_duplicates:['b@x.com'], invalid:['oops']}` renders a summary naming all three, the textarea clears, `list` refetches.
- A failing `add` renders `role="alert"` and **keeps** the textarea content.
- Note editing: inline edit + confirm → `updateNote(id, text)`, new note shown.
- Delete: opens `ConfirmModal` whose text states plainly that deleting does not remove an existing account (assert that clause); confirming calls `remove(id)` and refetches; cancelling calls nothing.
- A failed initial `list` renders `CatalogLoadFailed` (or equivalent text), not a blank page.
- Navigation: in admin mode the sidebar shows **Alpha** after **Import**; in user mode it is absent; `/discover/alpha` outside admin mode redirects to `/discover`.

**Implement:** reuse `Card`, `Badge`, `Button`, `Input`, `ConfirmModal`, `CatalogNoticeBar`, `CatalogLoadFailed`, `mutedTextStyle`, and `apiErrorText` / `asSentence` from `catalogApi`; follow the `SystemVocabularyPage` shape (hand-rolled `ul` inside a flush `Card`) rather than inventing a table primitive. Per `MEAL_PLANNER_DESIGN_GUIDE.md`: `Signed up` in `--c-pos`, `Invited` neutral, 44 px tap targets, ghost/secondary button hierarchy. `// ALPHA-GATE` on the page header and on the `App.jsx` / `Sidebar.jsx` lines.

**Verify:** from `frontend-v2/`: `npm run test`, then `npm run lint`.

---

## WAVE 3 (sequential — D7 ordering)

### I1 — Automated integration verification (orchestrator)
A1, F1, A2, F2 all merged into `feature/alpha-allowlist`, then from `backend/`:
```powershell
docker start mp_test_pg
$env:TEST_DATABASE_URL='postgresql://user:pass@localhost:5432/mealsdb_test'; python -m pytest
python -m flake8 .
```
from `frontend-v2/`: `npm run test`; `npm run lint`; `npm run build`.

Then `git grep -n "ALPHA-GATE"` and check the output is exactly the spec's inventory: the four alpha files (+ their tests + the migration) plus **three** `main.py` lines, **one** `App.jsx` line, **one** `Sidebar.jsx` entry, **one** seed block. Anything else is a leak of the feature into the codebase and must be fixed before proceeding.

### S1 — `/simplify` + docs sweep (orchestrator)
1. Run the **`/simplify`** skill over `git diff main...HEAD` and apply its fixes. Likely candidates: count/summary phrasing duplicated between the add summary and the header counts; copy helpers that belong beside the existing `catalog/` ones.
2. `CLAUDE.md` Architecture: add `alpha_routes.py` to the router list and `alpha.py` to the backend layers, each annotated **"temporary — closed-alpha scaffolding, removed with the alpha (ALPHA-GATE)"**, plus `AlphaPage` under `pages/`.
3. Re-run the full I1 gate (pytest incl. migrations, flake8, vitest, eslint, build) to prove `/simplify` broke nothing.

### P1 — Manual UI pass → **PAUSE (user testing)**
`docker compose down -v; docker compose up --build`, then present this checklist verbatim and wait for the user's go-ahead:

1. Open http://localhost:3000, log in as `demo@mealplanner.test` / `demo1234`, switch to admin mode. The sidebar shows **Alpha** after Import.
2. The header counts the seeded invites; demo/friend/guest show **Signed up**, `alpha-pending@mealplanner.test` shows **Invited**.
3. Paste `one@example.com, two@example.com` plus a deliberately broken line and press **Add invites**. The summary reports two added and one invalid; the rows appear.
4. Press **Add invites** again with the same text: everything is reported as already listed, and no duplicate row appears.
5. Edit a note inline and reload — it persisted.
6. Log out and register a brand-new account with an address that is **not** listed. The error reads "Meal Planner is in a closed alpha. This email address hasn't been invited yet."
7. Register with `one@example.com` — it succeeds; the verification link is in the `backend` container log.
8. Back as the admin, delete `two@example.com`; confirm the dialog says deleting does not remove an existing account. Then delete `friend@mealplanner.test`'s invite and confirm that account can still log in.
9. Switch to user mode: the Alpha row is gone and `/discover/alpha` bounces to Discover.

Finally, report the spec's removal checklist against the real `git grep -n "ALPHA-GATE"` output, so the exit path is verified on the way in.

---

## Spec ambiguities, resolved

1. **`alpha.py`'s import list excludes `pydantic`**, yet the spec wants per-entry validation with "the same email validation the rest of the app uses" *and* invalid addresses to be non-fatal. Both cannot hold with validation in a Pydantic field. → D4.
2. **Duplicate normalisation.** The spec gives `alpha.py` "email normalization" while `models.normalize_email` already exists. → D3: one-line re-export.
3. **`signed_up_at` is unnamed** in the spec ("that user's `created_at`"). Frozen as `signed_up_at`, null when `signed_up` is false.
4. **POST field name unspecified.** Frozen as `emails` — the single contract F1 and A2 must agree on without talking, so it is pinned twice: by F1's serialised-body assertion and A2's 422 test.
5. **DELETE status code unspecified.** Frozen as **204, no body** — deliberately unlike the catalog admin DELETEs, since there is nothing to report.
6. **`invited_by_user_id` "null if user deleted"** with no user-delete route today. Frozen as `ON DELETE SET NULL`, so the stated behaviour is the database's rather than a future code path's.
7. **Fail-open is untestable manually once seeded** (D9 gates every local environment). It is covered only by A1's empty-table unit test, inside its own transaction. Recorded in the final report.
8. **Sidebar colour token** is unspecified and every obvious category hue is taken; F2 chooses from the design guide and reports the choice — the one open aesthetic decision.

## Critical files

- [backend/main.py](backend/main.py) — include_router block (106-112), `register` (460-524), `login_with_google` (581-626)
- [backend/models.py](backend/models.py) — `normalize_email` (165-173), `User` (176-266)
- [backend/catalog_admin_routes.py](backend/catalog_admin_routes.py) — router idiom (74-78)
- [backend/tests/test_catalog_admin.py](backend/tests/test_catalog_admin.py) — 401/403 sweep template (158-191)
- [backend/tests/test_architecture_guards.py](backend/tests/test_architecture_guards.py) — `_imported_modules`, `_production_modules`
- [backend/scripts/seed_testing_data.py](backend/scripts/seed_testing_data.py) — `populate` (934-1014)
- [frontend-v2/src/pages/SystemVocabularyPage.jsx](frontend-v2/src/pages/SystemVocabularyPage.jsx) — the page template
- [frontend-v2/src/App.jsx](frontend-v2/src/App.jsx) — `AdminOnlyRoute` (81-83), admin routes (189-201)
- [frontend-v2/src/components/Sidebar.jsx](frontend-v2/src/components/Sidebar.jsx) — NAV array (24-39)
