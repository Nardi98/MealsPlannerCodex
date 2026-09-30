# Alpha email allowlist — design

Date: 2026-09-30
Status: approved, ready for planning

## Problem

The closed alpha must be invitation-only: only email addresses the admin has
listed may create an account. The admin needs a screen to manage that list.

This is temporary scaffolding. When the alpha ends the whole feature is
deleted, so it is designed for removal above all else.

## Scope

In scope: the allowlist table, the signup gate, the `/admin/alpha/*` routes,
and the Alpha admin page.

Out of scope (explicitly): the feedback system (its own spec and cycle), any
invitation email, any "request access" flow, and any change to login, refresh,
password reset, or existing accounts.

## Governing constraint: atomic and removable

Every artifact of this feature carries the grep-able marker `ALPHA-GATE` in a
comment. No existing module may import alpha code; all dependency arrows point
into the feature.

Artifacts:

- `backend/alpha.py` — the domain: email normalization, `assert_email_allowed`,
  list/add/update/delete. Imports only `models`, `database`, SQLAlchemy and
  FastAPI's `HTTPException`. Imported by nothing except `alpha_routes.py` and
  the two `main.py` call sites.
- `backend/alpha_routes.py` — the `/admin/alpha/*` router. Every route behind
  `auth_users.require_admin`. Pydantic models are local to the file, following
  the convention of `catalog_admin_routes.py`; nothing is added to
  `schemas.py`.
- `backend/migrations/versions/<rev>_alpha_invites.py` — the table.
- `frontend-v2/src/pages/AlphaPage.jsx`, `frontend-v2/src/api/alphaApi.js`.

Marked lines in existing files (four, each with an `# ALPHA-GATE` /
`// ALPHA-GATE` comment):

1. `main.py` — `include_router(alpha_routes.router)`.
2. `main.py` — the guard in `register`.
3. `main.py` — the guard in `login_with_google`'s account-creation branch.
4. `frontend-v2/src/components/Sidebar.jsx` — the Alpha nav row.
   (`App.jsx`'s route line and `seed_testing_data.py`'s rows are marked the
   same way.)

Removal is: delete the listed files, delete the marked lines, drop the table.

## Data model

New table `alpha_invites`:

| column               | type                | notes                              |
|----------------------|---------------------|------------------------------------|
| `id`                 | Integer PK          |                                    |
| `email`              | String, unique, idx | stored normalized                  |
| `note`               | String, nullable    | free text, admin's own reminder    |
| `invited_by_user_id` | FK `users.id`, null | who added it; null if user deleted |
| `created_at`         | DateTime, not null  | `server_default=func.now()`        |

Normalization is `email.strip().lower()`, applied on write and on every lookup,
so the stored value is the only form that exists.

Per the repository's mandatory rule, the Alembic revision lands in the same
commit as the model change, and `backend/scripts/seed_testing_data.py` is
updated to insert a small coherent set of invites (including the emails of the
accounts it seeds) so the seeded database stays consistent.

## Gate behaviour

`alpha.assert_email_allowed(db, email)`:

1. If `alpha_invites` has **zero rows** → allow. The gate fails **open**: a
   fresh, wiped, or half-migrated database must never lock every prospective
   user out, and there is no separate kill switch by decision.
2. Else if the normalized email matches a row → allow.
3. Else raise a 403 whose detail reads: "Meal Planner is in a closed alpha.
   This email address hasn't been invited yet."

There is no environment variable and no UI toggle. When the alpha ends the
feature is removed, which is the off switch.

Call sites:

- `POST /auth/register` — the guard runs **before** the existing duplicate-email
  lookup. This preserves that endpoint's deliberate anti-enumeration property:
  a 403 discloses only that an address is not invited, never whether an account
  exists for it.
- `POST /auth/google` — the guard runs only inside the `user is None` branch,
  i.e. only when Google sign-in would *create* an account. An existing user
  signing in with Google is never gated.

Login, token refresh, email verification and password reset are untouched.
Removing an entry blocks a future signup and nothing else; accounts already
created keep working. Accounts that predate the list are unaffected, since the
gate exists only on the creation path.

## Routes

All under `/admin/alpha`, all behind `auth_users.require_admin` (the server is
the only enforcement; admin *mode* in the frontend is presentation only).

- `GET /admin/alpha/invites` — every entry, newest first, each with a derived
  `signed_up: bool` (a `User` row exists with that email) and, when true, that
  user's `created_at`. The derivation is a join at read time; no denormalized
  state to keep in sync.
- `POST /admin/alpha/invites` — body is a single free-text field of emails
  separated by newlines and/or commas, so pasting a list is one action and a
  single add is just the one-email case. Returns
  `{added: [...], skipped_duplicates: [...], invalid: [...]}`. Entries are
  validated with the same email validation the rest of the app uses; an invalid
  address is reported, not fatal to the batch.
- `PATCH /admin/alpha/invites/{id}` — the note only. Emails are not editable;
  delete and re-add instead, so the audit trail of `created_at` stays honest.
- `DELETE /admin/alpha/invites/{id}` — removes the entry.

## Admin UI

Route `/discover/alpha`, rendered by `AlphaPage`, gated by the existing
`AdminOnlyRoute` in `App.jsx` (which redirects to `/discover` outside admin
mode). A fourth admin-only sidebar row, "Alpha", after Import — the admin
surfaces stay grouped under the `/discover` prefix by convention.

One screen, built from `components/` primitives and following
`MEAL_PLANNER_DESIGN_GUIDE.md`:

- Header with counts: *N invited · M signed up*.
- An add box: a textarea plus an "Add invites" button, showing the result
  summary (added / already listed / invalid) after submission.
- A table: Email; Status badge (`Signed up` in `--c-pos`, `Invited` neutral);
  Note, inline-editable; Added date; a delete action whose confirmation states
  plainly that deleting does not remove an existing account.
- Empty state: an explicit warning that there are no invites and **signup is
  therefore open to everyone** — the fail-open case must be visible, not
  inferred.

All requests go through `api/client.js`'s `request()` helper, as every other
api module does.

## Testing

Implementation follows the repository's mandated TDD workflow.

Backend:

- `alpha.py` unit tests: normalization (case, surrounding whitespace); the
  empty-table open case; an allowed email; a rejected email and its 403 detail.
- Call-site tests: registration rejected for an uninvited email; accepted for
  an invited one; Google sign-up rejected for an uninvited new email; an
  existing Google user signing in is *not* gated; login of an existing account
  whose email is not listed still succeeds.
- Router tests: each `/admin/alpha/*` route returns 403 for a non-admin and
  401 unauthenticated; the batch add's added/duplicate/invalid partitioning;
  note update; delete.
- `tests/test_architecture_guards.py`: `alpha.py` imports no router and no
  `main`; and no module outside the alpha files imports `alpha` except the
  marked `main.py` lines.
- `tests/test_migrations.py` continues to pass, proving the revision matches
  the model.

Frontend: vitest coverage of `AlphaPage` — list rendering with both status
badges, the empty/open-signup warning, a batch add and its result summary, and
the delete confirmation.

## Removal checklist (for when the alpha ends)

1. `grep -rn "ALPHA-GATE"` and delete every marked line.
2. Delete `backend/alpha.py`, `backend/alpha_routes.py`,
   `frontend-v2/src/pages/AlphaPage.jsx`, `frontend-v2/src/api/alphaApi.js`,
   and their tests.
3. Add an Alembic revision dropping `alpha_invites`, and remove the seed rows.
