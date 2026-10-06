# Feedback system — design

Date: 2026-09-30
Status: approved, ready for an implementation plan

## Purpose

Give every signed-in user a discrete way to report a problem or ask for a change
from whatever page they are on, and give the admin one screen to read, organise
and close what arrives.

The alpha's feedback currently arrives by word of mouth, which means it is not
counted, not searchable and lost when a conversation ends. This replaces that
with rows in the database.

## Scope

In scope: capture (a modal reachable from every page) and triage (an admin page).

Out of scope, deliberately:

- **Nightly Claude triage.** Wanted, but designed separately once real feedback
  exists. It needs nothing from the app beyond a read path and a place to write
  its analysis, and this design provides both (see *Future: assisted triage*).
- **Any reply channel to the user.** Submitting is fire-and-forget. During a
  closed alpha the admin already has every tester's email address, so a reply
  thread would be a second, worse inbox.
- **A user-facing list of one's own feedback.** Follows from the above.

## Data model

One Alembic revision in the same commit as the model change, per `CLAUDE.md`,
and `scripts/seed_testing_data.py` updated in the same change.

### `FeedbackItem` (`feedback_items`)

| column | type | notes |
| --- | --- | --- |
| `id` | int PK | |
| `ref_code` | str, unique, indexed | `FB-<id>`, assigned at insert. Human-readable; quotable in a commit message or an email to a tester. |
| `title` | str, not null | |
| `body` | text, not null | |
| `type` | enum `feedback_type_enum` | `issue`, `request`, `improvement`, `not_working` |
| `status` | enum `feedback_status_enum`, default `open` | `open`, `in_progress`, `closed_fixed`, `closed_ignored` |
| `seen` | bool, default `false` | The unread axis. |
| `priority` | enum `feedback_priority_enum`, default `normal` | `low`, `normal`, `high` |
| `user_id` | FK `users.id` `ON DELETE SET NULL` | The item outlives the account that filed it. |
| `page_path` | str, nullable | Captured silently from the router. |
| `user_agent` | str, nullable | Captured silently. |
| `viewport_width` | int, nullable | Captured silently; separates mobile-only bugs from desktop ones. |
| `screenshot_key` | str, nullable | A `storage.py` object key. |
| `admin_notes` | text, nullable | Private. Never appears in any user-facing response. |
| `created_at` / `updated_at` | datetime | `server_default=func.now()`; `updated_at` refreshed on update. |

**Why `status` and `seen` are separate fields.** They are orthogonal axes: a
closed item can still be unread, and an item can be read and still open. A
single enum containing `unread` would destroy the unread count the moment an
item is triaged.

**Why `ref_code` is derived from `id`.** No counter table, no collision, no
second source of truth. It is written in the same transaction as the insert.

### `FeedbackTag` (`feedback_tags`) and `feedback_item_tags`

`FeedbackTag`: `id`, `name` (unique, normalized — trimmed, lowercased, inner
whitespace collapsed). `feedback_item_tags`: a plain many-to-many join with
`ON DELETE CASCADE` on both sides.

**Why not the existing `Tag` table.** Recipe tags and feedback tags are
different vocabularies for different audiences. Sharing one table would put
`shopping-list-bug` into every user's recipe tag picker.

Tags are created on the fly: the admin types a name that does not exist and the
service creates it. Normalization is what makes that safe — `Mobile` and
`mobile ` are the same tag, so the filters do not fragment.

## Backend

### `feedback.py` — the domain logic

Imports only `models` and `storage`; it must not import `main` or any router,
asserted by `tests/test_architecture_guards.py` alongside `catalog` and `alpha`.
Same shape as those modules: the routers translate HTTP and nothing else.

```
submit(db, user, title, body, type, page_path, user_agent,
       viewport_width, screenshot) -> FeedbackItem
list_items(db, *, status=None, type=None, priority=None,
           tag=None, seen=None) -> list[FeedbackItem]   # newest first
get_item(db, item_id) -> FeedbackItem | None
mark_seen(db, item) -> FeedbackItem
set_status(db, item, status) -> FeedbackItem
set_priority(db, item, priority) -> FeedbackItem
set_notes(db, item, notes) -> FeedbackItem
set_tags(db, item, names) -> FeedbackItem      # creates missing tags
list_tags(db) -> list[FeedbackTag]
rename_tag(db, tag, name) -> FeedbackTag
unseen_count(db) -> int
```

`submit` stores the screenshot through `storage.save_image`, which already
raises `ValueError` for a non-image content type; the route turns that into a
400 and no row is written.

### `feedback_routes.py` — the user's one route

`POST /feedback`, multipart (fields plus an optional image part), requires an
authenticated user.

Rate limited with the existing `ratelimit` module — `user_or_ip_key`, a new
`FEEDBACK_RATE_LIMIT` defaulting to `"10/hour"` and env-overridable like its
siblings. Per-user rather than per-address is the right key here for the same
reason it is for sharing. Ten an hour is far more than honest use needs and caps
what a retry loop or a bored tester can put in the table; each row can carry an
image, so rows are not cheap.

The response body is `{ "ref_code": "FB-104" }` and nothing else. There is no
list or read endpoint for users: a user cannot read back any feedback, their own
included.

### `feedback_admin_routes.py` — everything else

Prefix `/admin/feedback`, with `require_admin` as a **router-level** dependency,
matching `alpha_routes` and `catalog_admin_routes`. A non-admin gets one fixed
403 before any route code runs — identical whether the id exists or not — and an
anonymous caller gets 401. Gating at the router rather than per route means a
forgotten `Depends` cannot happen.

| route | purpose |
| --- | --- |
| `GET /admin/feedback` | list, with the `list_items` filters as query params |
| `GET /admin/feedback/unseen-count` | the sidebar badge |
| `GET /admin/feedback/{id}` | detail, including `admin_notes` |
| `PATCH /admin/feedback/{id}` | `status`, `priority`, `admin_notes`, `tags`, `seen` — each optional |
| `GET /admin/feedback/{id}/screenshot` | streams the bytes via `storage.open_image` |
| `GET /admin/feedback/tags` | the vocabulary, for the filter bar and the tag input |
| `PATCH /admin/feedback/tags/{id}` | rename |

Writes are rate limited with a `FEEDBACK_ADMIN_RATE_LIMIT` default of
`"240/hour"` — triage is many small edits, so it sits higher than the catalog's
admin limit.

Pydantic models are defined locally in each router rather than added to
`schemas.py`, following `catalog_admin_routes` and `alpha_routes`.

Both routers are wired with `include_router` in `main.py`; no route logic is
added to `main.py`.

### Screenshots are admin-gated

Recipe images are served from a guessable public path, which is right for
recipes. A feedback screenshot may show a user's own meal plan, so it is served
only through `GET /admin/feedback/{id}/screenshot`, behind `require_admin`. The
object key is never published to a user-facing response.

## Frontend

### Capture

`components/FeedbackModal.jsx` — title, body, a type segmented control, and an
optional image picker. Built on the existing `Modal`, `Input`, `Button` and
`SegmentedControl` primitives and `MEAL_PLANNER_DESIGN_GUIDE.md`.

It reads its own context: `useLocation().pathname`, `window.innerWidth`,
`navigator.userAgent`. The user is told, in one line of the modal, that the page
they are on is included.

Opened from a **"Send feedback"** row in `components/ProfileMenu.jsx`. The
profile menu is already on every page, which makes this present everywhere with
no layout risk and no collision with the mobile `Fab`. On success the modal
shows the ref code, then closes.

`api/feedbackApi.js` holds the one call, through `api/client.js`'s `request()`.

### Triage

`pages/FeedbackAdminPage.jsx` at `/discover/feedback`, wrapped in
`AdminOnlyRoute` in `App.jsx`. `api/feedbackAdminApi.js` holds its calls.

Layout: a filter bar (status, type, priority, tag, unread-only), a list of rows
— ref code, title, type badge, status chip, priority, tags, author, date — and a
detail view for the selected row showing the body, the screenshot, and controls
for status, priority, tags (typing a new name creates it) and admin notes.
Opening a row marks it seen.

One new `ADMIN_ONLY` entry in `components/Sidebar.jsx`:

```js
{ label: 'Feedback', path: '/discover/feedback',
  Icon: ChatBubbleLeftEllipsisIcon, color: 'var(--cat-berry)',
  modes: ADMIN_ONLY, match: (p) => p === '/discover/feedback' }
```

Berry is the colour: every distinct hue in the palette is already spoken for,
but berry's only other use is user-only *Recipes*, so within the admin menu it
is unambiguous. Sage and forest alias the panel's own green and would vanish
into it.

The entry carries the unseen count as a badge. The exhaustive admin-nav
assertion in `components/__tests__/Sidebar.test.jsx` is updated, as it was for
Alpha.

## Testing

Test-driven, per `CLAUDE.md` — each behaviour below is a failing test first.

Backend:

- submit: happy path; missing title or body rejected; unknown `type` rejected;
  `ref_code` is `FB-<id>`; `page_path`, `user_agent`, `viewport_width` stored.
- submit with an image: stored and readable back; a non-image content type is a
  400 and writes no row.
- rate limit: the `n+1`-th submission inside the window is a 429.
- authorization: a parametrized sweep asserting **every** `/admin/feedback/*`
  route returns 403 for a signed-in non-admin and 401 anonymous, the screenshot
  stream included.
- `admin_notes` and `screenshot_key` appear in no user-facing response.
- `status` and `seen` move independently; closing an item does not mark it seen.
- tags: inline creation; a differently-cased or padded name reuses the existing
  tag; rename; filtering by tag.
- `unseen_count` matches the rows.
- architecture guard: `feedback` imports neither `main` nor any router.
- `tests/test_migrations.py` agrees with the models (it already fails on drift).

Frontend (vitest):

- the modal submits the captured page path and shows the returned ref code;
- validation blocks an empty title;
- the admin page filters by status and by tag, and marks a row seen on open;
- `Sidebar` shows Feedback in admin mode and not in user mode.

Seed: `scripts/seed_testing_data.py` inserts a coherent handful of feedback
items spread across types, statuses, priorities and a few tags, one of them
carrying a screenshot — mandatory, since the schema changes.

## Future: assisted triage (not built here)

Recorded so the data model above is understood as deliberate — not so it is
built now.

Claude never runs inside the website. The shape, when built, is a scheduled
Claude Code session outside the app that authenticates as an admin against the
routes above, reads the open items, and writes its analysis into `admin_notes`.
It proposes; it does not commit code, and it touches no column but that one.

That is why `admin_notes` exists now. Because the integration is a client of an
API that already exists, it adds no attack surface to the application: there is
no agent embedded in the site, no tool loop reachable from a request, and
nothing extra to reach even if the session's credentials leaked — they grant
only what an admin already has. An in-app agent would be the shape worth
fearing, and this design makes it unnecessary.
