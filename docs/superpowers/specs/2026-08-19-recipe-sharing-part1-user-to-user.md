# Requirements — Part 1: User-to-User Recipe Sharing

**Status**: Draft for review
**Date**: 2026-08-19
**Release**: Current release. Intended to ship on its own.
**Companion**: [Part 2 — Public Publishing & Social Discovery](2026-08-19-recipe-sharing-part2-public-publishing.md),
deliberately deferred.

Requirement keywords: **MUST** = mandatory. **MUST NOT** = prohibited. **SHOULD** =
strongly recommended, deviation requires written justification. **MAY** = optional.
Each requirement carries a stable ID for traceability to tests.

---

## 1. Context

### 1.1 Current state

Meal Planner is private per account. Every `Recipe`, `Ingredient`, and `Tag` carries a
`user_id` owner column (`_owner_fk_column()`, [models.py](../../../backend/models.py)) and
is invisible to every other account. `User` has `email` and `display_name`, but no stable
public identifier. The frontend (`frontend-v2/`) is a client-rendered Vite SPA. There is no
unauthenticated surface of any kind.

### 1.2 What this part delivers

A user can send one specific recipe to one specific person — including someone with no
account — by generating a link and forwarding it themselves over their own channel
(typically WhatsApp). The recipient can read the recipe, and, if they have an account, copy
it into their own recipe book, where they own and can freely edit it, while permanent
credit to the original author is preserved.

### 1.3 What this part deliberately excludes, and why

Publishing recipes to the open web is **not** in this release. The moment user content is
publicly indexable, the product acquires an obligation to moderate it, to handle reports
and takedowns, and to carry terms of service and a privacy policy. That obligation is not
one the project is currently prepared to take on. Part 2 exists precisely so that decision
can be made deliberately and later.

Concretely deferred to Part 2: public visibility, indexable recipe pages, SEO and
structured data, public profile pages, cross-user search, ratings, content screening,
reporting, and administrative moderation.

### 1.4 The forward-compatibility constraint

This release **MUST** be built so that Part 2 is **additive**: new fields, new routes, and
new templates, but no rework of what Part 1 ships. §9 states this as testable requirements.
It is the primary architectural constraint on this part, and it is the reason several
choices here are more structured than a one-to-one sharing feature would strictly need.

### 1.5 Objectives

| # | Objective |
|---|---|
| O-1 | A user can share one recipe with one person, whether or not that person has an account. |
| O-2 | The recipient can read the shared recipe with no account, no login, and no JavaScript. |
| O-3 | A recipient with an account can copy the recipe into their own book and edit it freely. |
| O-4 | Copies permanently credit the original author. |
| O-5 | Sharing leaks no private data beyond the shared recipe itself. |
| O-6 | Everything above is built so Part 2 adds capability without reworking it. |

---

## 2. Glossary

| Term | Definition |
|---|---|
| **Owner** | The `User` whose `user_id` is on the `Recipe` row. |
| **Visibility** | The `private` / `unlisted` / `public` state of a recipe. In this release `public` is defined but unreachable. |
| **Share** | A `RecipeShare` row granting access to one recipe through a secret token URL. |
| **Share page** | The server-rendered HTML page at `/s/{token}` that a recipient reads. |
| **Copy** | An independent `Recipe` duplicated from a source recipe into another user's book. |
| **Source** | The recipe a copy was made from. |
| **Attribution** | The permanent, non-removable credit line on a copy naming its source. |
| **Handle / username** | A user's unique public identifier. Displayed in this release; linkable in Part 2. |

---

## 3. Rendering Requirements

The share page is read by people with no account, over WhatsApp. That constrains the
rendering technology, so it is stated as a requirement rather than left open.

| ID | Requirement |
|---|---|
| RA-1 | The share page **MUST** be rendered server-side by the FastAPI backend as complete HTML. The full recipe content **MUST** be present in the initial HTTP response body. |
| RA-2 | The share page **MUST** be fully readable with JavaScript disabled. |
| RA-3 | The share page **MUST** be reachable with no authentication and **MUST NOT** require a session cookie to render. |
| RA-4 | The authenticated SPA **MUST** continue to function unchanged. This work **MUST NOT** require migrating the SPA to server-side rendering. |
| RA-5 | Public-facing page styling **MUST** derive from a single stylesheet expressing the tokens of `MEAL_PLANNER_DESIGN_GUIDE.md`. Design values **MUST NOT** be duplicated as literals across templates. |
| RA-6 | The share page **MUST** be produced by a **block renderer** driven by an ordered list of typed blocks, even though this release only ever renders one fixed default block list. |
| RA-7 | The share page **MUST** emit OpenGraph and Twitter card tags (`og:title`, `og:description`, `og:image`, `og:url`) sufficient to unfurl with a title and image in WhatsApp, Telegram, and Facebook. |
| RA-8 | The share page **MUST** emit `<meta name="robots" content="noindex,nofollow">`. |
| RA-9 | The share page **MUST NOT** emit `schema.org` structured data, a canonical link, or any other indexing signal. |

**Rationale for RA-1**: the recipient may have no account, so a page requiring the
authenticated SPA is unusable to them. Independently, WhatsApp, Telegram, Facebook,
iMessage, and Slack unfurlers do not execute JavaScript; a client-rendered share link would
arrive as a blank grey card, which materially undermines the feature's only delivery
channel.

**Rationale for RA-6 and RA-5**: these cost almost nothing now and are the entire reason
Part 2's page renderer is a configuration change rather than a rewrite. See §9.

**Rationale for RA-8 and RA-9**: this release must produce *no* indexable surface. The
share page is the one public URL that exists, and it must be invisible to search engines,
so that the decision to publish content to the web remains genuinely unmade.

---

## 4. Visibility Requirements

| ID | Requirement |
|---|---|
| VIS-1 | `Recipe` **MUST** have a `visibility` field admitting exactly three values: `private`, `unlisted`, `public`. All three **MUST** be defined in this release. |
| VIS-2 | `private` **MUST** be the default for every newly created recipe, including copies and imported recipes. |
| VIS-3 | A `private` recipe **MUST** be accessible only to its owner, through authenticated endpoints, and **MUST NOT** have any reachable unauthenticated URL. |
| VIS-4 | An `unlisted` recipe **MUST** be reachable only through a valid, non-revoked, non-expired share token. |
| VIS-5 | In this release, no code path **MUST** be able to set `visibility = public`. Any attempt through the API **MUST** be rejected with HTTP 400 and a message stating the capability is not yet available. |
| VIS-6 | Creating the first active share on a `private` recipe **MUST** automatically promote it to `unlisted`. |
| VIS-7 | Revoking or expiring the last active share on an `unlisted` recipe **MUST** demote it to `private`. |
| VIS-8 | Only the owner **MUST** be able to change a recipe's visibility. |
| VIS-9 | Visibility **MUST** be enforced in the data-access query layer, not in templates and not in the frontend. |
| VIS-10 | An automated test **MUST** assert that a `private` recipe is unreachable through every unauthenticated route, and that setting `public` is rejected. |

**Rationale for VIS-1 and VIS-5**: the three-state field is introduced now, with `public`
inert, so that Part 2 enables a value rather than migrates a column. Retrofitting a
visibility model onto a shipped share feature is exactly the rework §9 forbids.

---

## 5. Share Requirements

### 5.1 Creation and delivery

| ID | Requirement |
|---|---|
| SH-1 | The system **MUST NOT** send the share message on the user's behalf. Creating a share **MUST** return a URL that the user copies and delivers through their own channel. |
| SH-2 | A share token **MUST** be generated from a cryptographically secure source with at least 128 bits of entropy, and **MUST NOT** be derivable from the recipe id, user id, title, or any timestamp. |
| SH-3 | Share tokens **MUST** be stored hashed. Read access to the database **MUST NOT** yield usable share URLs. |
| SH-4 | Each share **MUST** carry a `mode`, chosen by the sharer per share: <br>• `link` — anyone possessing the URL may read the recipe, with no authentication. <br>• `person` — only the named recipient may read it, and **MUST** be authenticated as the matching account, or have verified the named email address, to do so. |
| SH-5 | For `mode = person` a recipient (account or email address) **MUST** be required. For `mode = link` a recipient **MUST** be optional. |
| SH-6 | When a recipient is named on a `link`-mode share, the only effect **MUST** be that the recipe appears in that account's "Shared with me" list. It **MUST NOT** restrict who may open the URL. |
| SH-7 | The share dialog **MUST** state explicitly, for `mode = link`, that anyone who receives the link can open the recipe. The interface **MUST NOT** imply that naming a recipient restricts access in `link` mode. |
| SH-8 | The share dialog **MUST** present the two modes in plain language describing their actual effect, not by their internal names. |
| SH-9 | A share **MAY** carry an expiry timestamp, set by the sharer at creation. |
| SH-10 | The system **MAY** send a notification email to a named recipient containing the link and, where the address has no account, a sign-up prompt. The link **MUST** function regardless of whether that email is delivered or opened. |
| SH-11 | Share creation **MUST** be rate-limited per user, reusing the existing rate-limiting mechanism. |
| SH-12 | The share control **MUST** be reachable from the existing recipe modal in the SPA. |

**Rationale for SH-7**: this was the sharpest tension in the original concept. A link that
grants access is a *credential*; naming a recipient alongside it does not restrict who can
open it once forwarded. Implying otherwise would be a security-relevant lie to the user, so
the honest disclosure is a requirement rather than a copywriting detail.

### 5.2 Access and revocation

| ID | Requirement |
|---|---|
| SH-20 | The owner **MUST** be able to list every share on a recipe, showing mode, recipient, creation date, last-viewed date, and expiry, and **MUST** be able to revoke each one individually. |
| SH-21 | An expired share **MUST** be treated exactly as a revoked share. |
| SH-22 | Opening a revoked, expired, or nonexistent token **MUST** return HTTP 404 with a neutral message, and **MUST NOT** reveal whether the token ever existed, or which recipe or user it referred to. |
| SH-23 | Opening a `person`-mode share while unauthenticated **MUST** prompt sign-in and return the visitor to the share URL on success. |
| SH-24 | Opening a `person`-mode share as a different account **MUST** return HTTP 403, and **MUST** identify the required address only in masked form (e.g. `a•••@g•••.com`). |
| SH-25 | Deleting a recipe **MUST** revoke all of its shares. |
| SH-26 | Viewing a share **MUST** update its `last_viewed_at`. The system **MUST NOT** record a per-visit log, visitor identity, or IP address for share views. |
| SH-27 | Token lookup **MUST** be constant-time with respect to token validity, and **MUST NOT** allow enumeration through response-time differences. |
| SH-28 | Share tokens **MUST NOT** appear in `Referer` headers sent to third parties; the share page **MUST** set an appropriate referrer policy. |

### 5.3 "Shared with me"

| ID | Requirement |
|---|---|
| SWM-1 | An authenticated user **MUST** have a "Shared with me" list containing every recipe for which a non-revoked, non-expired share names them by account id, or by an email address matching their own **verified** address. |
| SWM-2 | Entries **MUST** be read-only. The only permitted actions are *view* and *copy to my book*. |
| SWM-3 | A user **MUST** be able to dismiss an entry from their own list without affecting the underlying share. |
| SWM-4 | An unverified email address **MUST NOT** grant membership of this list. |
| SWM-5 | Recipes in this list **MUST NOT** appear in the user's own recipe list, planner candidates, or shopping list until copied. |

**Rationale for SWM-5**: shared recipes must not silently enter the planner's candidate
pool. The planner scores and schedules recipes the user owns; a borrowed recipe becoming
plannable without an explicit copy would surprise the user and corrupt their meal history.

---

## 6. Share Page Content Requirements

| ID | Requirement |
|---|---|
| SP-1 | The share page **MUST** render, in this default order: hero (image, title, author name and handle), ingredients with quantities and units, steps, attribution when the recipe is itself a copy, and an author card. (`notes` struck: `Recipe` has no such column and §11.2 does not add one, so no `notes` block type is registered.) |
| SP-2 | The page **MUST** display a servings figure, and **SHOULD** offer client-side ingredient scaling that degrades gracefully to the default servings without JavaScript. |
| SP-3 | The page **MUST** offer "Add to my recipe book", prompting sign-in when the visitor is unauthenticated and returning them to the page afterwards. |
| SP-4 | The page **MUST** be responsive and legible on mobile viewports. |
| SP-5 | The page **MUST** follow `MEAL_PLANNER_DESIGN_GUIDE.md`. |
| SP-6 | The page **MUST** have exactly one `<h1>`, use semantic sectioning elements, and provide meaningful `alt` text on every image. |
| SP-7 | The page **MUST NOT** render a rating control, a report control, a search bar, or a link to any profile page. Those belong to Part 2. |
| SP-8 | The page **MUST NOT** link to, or otherwise disclose the existence of, any other recipe belonging to the owner. |
| SP-9 | All user-supplied outbound links rendered on the page **MUST** carry `rel="nofollow ugc"`. |
| SP-10 | All user-supplied text **MUST** be rendered through a strict sanitiser allowlist (bold, italic, links, lists, headings, line breaks). Content outside the allowlist **MUST** be stripped. |
| SP-11 | The system **MUST NOT** accept, store, or render user-supplied HTML, CSS, or JavaScript. This is a permanent prohibition, not a deferral. |

---

## 7. Copy and Attribution Requirements

### 7.1 Copying

| ID | Requirement |
|---|---|
| CP-1 | An authenticated user **MUST** be able to copy any recipe reachable through a valid share, provided they are not its owner. |
| CP-2 | A copy **MUST** be a full, independent duplicate: its own `Recipe` row owned by the copier, its own `RecipeIngredient` rows, and its own tag associations. |
| CP-3 | Ingredients and tags **MUST** be resolved-or-created inside the copier's own namespace, respecting `uq_ingredient_user_name` and `uq_tag_user_name`. A copy **MUST NOT** create any cross-user reference to another user's `Ingredient` or `Tag` rows. |
| CP-4 | A copy **MUST** be created with `visibility = private`. |
| CP-5 | Later edits to the source **MUST NOT** propagate to the copy, and edits to the copy **MUST NOT** affect the source. |
| CP-6 | Favorite-side links **MUST** be reproduced only where the referenced side recipe is also copied in the same operation; links the copier cannot access **MUST** be dropped silently. |
| CP-7 | Planner state on the source — `score`, `date_last_consumed`, `date_last_rejected` — **MUST NOT** be copied. The copy starts with no history, so the copier's planner is not seeded with someone else's behaviour. |
| CP-8 | The copy operation **MUST** be atomic. A partial copy **MUST NOT** be observable. |
| CP-9 | Copying **MUST** be rate-limited per user. |
| CP-10 | A user **MUST NOT** copy their own recipe through this mechanism. |
| CP-11 | Copying the same source twice **MUST** be permitted, and **SHOULD** warn the user that they already hold a copy. |

### 7.2 Attribution

| ID | Requirement |
|---|---|
| AT-1 | A copy **MUST** record its lineage: source recipe id, source user id, and **snapshotted** copies of the source author's username and the source recipe's title, together with the copy timestamp. |
| AT-2 | The snapshotted username and title **MUST** be used to render attribution when the source row or source account no longer exists. Deleting the source **MUST NOT** erase the credit. |
| AT-3 | The attribution line — of the form *"Adapted from **{title}** by **@{username}**"* — **MUST** be displayed on the copy in the authenticated recipe view, and on any share page for the copy. |
| AT-4 | The attribution line **MUST NOT** be editable, hideable, or removable by the copier, through any UI control, any API field, or any amount of subsequent editing. |
| AT-5 | There **MUST NOT** be any divergence, similarity, or edit-distance threshold that removes or weakens attribution. |
| AT-6 | Copying a copy **MUST** credit the immediate source only. Full ancestry chains **MUST NOT** be rendered. |
| AT-7 | The source recipe **MUST** display a "copied N times" count to its owner. The identities of copiers **MUST NOT** be exposed to anyone. |
| AT-8 | Re-sharing a copy **MUST** carry its attribution to the new share page. |

**Rationale for AT-5**: an automatic "modified enough to be mine" threshold was considered
and rejected. It is trivially defeated by renaming ingredients or padding the procedure; it
misjudges small but genuinely transformative changes; it requires perpetual tuning and its
own test surface; and it produces verdicts a user cannot reason about or contest. Permanent
credit is unambiguous, needs no tuning, and costs the copier nothing real.

---

## 8. Identity Requirements

Usernames land in this release even though there is no public profile page, because
attribution needs a stable, unique author identifier, and because adding a non-null unique
column later would require backfilling every existing account and interrupting every logged
-in user with a forced handle-selection prompt.

| ID | Requirement |
|---|---|
| UN-1 | `User` **MUST** have a `username` field that is non-null and unique. |
| UN-2 | Uniqueness **MUST** be case-insensitive and enforced by a database constraint, not only in application code. |
| UN-3 | A username **MUST** match `^[a-z0-9_]{3,30}$`, **MUST NOT** begin or end with `_`, and **MUST NOT** contain consecutive underscores. Input **SHOULD** be lowercased on entry rather than rejected for case. |
| UN-4 | A reserved-username list **MUST** exist and **MUST** include every current and planned root route segment — at minimum `r`, `s`, `api`, `static`, `assets`, `sitemap.xml`, `robots.txt` — plus `admin`, `administrator`, `support`, `help`, `about`, `login`, `logout`, `signup`, `register`, `settings`, `account`, `me`, `search`, `null`, `undefined`. Reserved names **MUST** be rejected. |
| UN-5 | A username **MUST** be chosen at registration for local sign-ups, on the existing registration form. |
| UN-6 | A Google-authenticated user without a username **MUST** be shown a mandatory, non-skippable handle-selection step before reaching the application. |
| UN-7 | An availability-check endpoint **MUST** be available to the registration form and **MUST** be rate-limited, so the handle space cannot be enumerated. |
| UN-8 | A user **MUST** be able to change their username, subject to a cooldown of at least 30 days. |
| UN-9 | On change, the previous username **MUST** be reserved for at least 30 days, during which it **MUST NOT** be claimable by another user. |
| UN-10 | The username **MUST** be displayed as plain text in this release. It **MUST NOT** be rendered as a link, since no profile page exists yet. |
| UN-11 | A user's email address **MUST NOT** be derivable from, or displayed alongside, their username on any unauthenticated surface. |

---

## 9. Forward-Compatibility Requirements

These exist so that Part 2 is additive. They are testable and are as binding as any other
requirement in this document.

| ID | Requirement |
|---|---|
| FC-1 | The block renderer of RA-6 **MUST** be the component Part 2 uses for public recipe pages. Enabling a public page **MUST NOT** require a second renderer, template engine, or frontend stack. |
| FC-2 | The `visibility` field **MUST** already admit `public` (VIS-1), so Part 2 removes a guard rather than migrating a column. |
| FC-3 | `Recipe` **MUST** already carry a nullable `page_layout` field, where `NULL` means "render the default block list". Every recipe in this release has `NULL`. Part 2's layout editor writes this field without a schema change. |
| FC-4 | `Recipe` **MUST** already carry a nullable `page_theme` field, unused in this release. |
| FC-5 | Attribution snapshots (AT-1) **MUST** already be captured, so that Part 2's public attribution line requires only rendering, not backfill. |
| FC-6 | The public serialiser of PRV-1 **MUST** be the same allowlist Part 2 extends. Part 2 **MUST** be able to add fields to it without restructuring it. |
| FC-7 | The public stylesheet of RA-5 **MUST** be reusable, unchanged, by Part 2's recipe and profile pages. |
| FC-8 | Usernames (§8) **MUST** already be unique and non-null, so Part 2 adds `/@{username}` without backfilling accounts or interrupting logged-in users. |
| FC-9 | This release **MUST NOT** introduce any indexable URL, structured data, sitemap, or `robots.txt` allowance. The decision to publish user content to the open web **MUST** remain unmade and reversible after this release ships. |
| FC-10 | An automated test **MUST** assert FC-9: that no route in this release returns a page lacking `noindex`, and that no sitemap or public discovery endpoint exists. |

---

## 10. Privacy Requirements

| ID | Requirement |
|---|---|
| PRV-1 | The share page and any unauthenticated response **MUST** be serialised through a dedicated public schema that **enumerates exactly the fields permitted to be exposed**. A denylist approach **MUST NOT** be used. |
| PRV-2 | The permitted fields are: recipe title, image URL, servings, procedure, ingredient names with quantities and units, tag names, course, author display name, author username, and the attribution snapshot. (`notes` struck — see SP-1.) |
| PRV-3 | The following **MUST NOT** appear in any unauthenticated response, rendered page, HTML comment, or embedded JSON: email addresses, numeric user ids, numeric recipe ids, `score`, `date_last_consumed`, `date_last_rejected`, `bulk_prep`, any meal-plan or meal data, `plan_settings`, `default_people`, share tokens, other shares on the same recipe, any other recipe belonging to the owner, or the identities of copiers. |
| PRV-4 | An automated test **MUST** assert that the set of fields emitted by the public serialiser **equals** the PRV-2 allowlist exactly, so that any future column added to `Recipe` is private by default and fails the test if silently exposed. |
| PRV-5 | Uploaded images are currently served without authentication by `GET /recipes/images/{key}` ([main.py:555](../../../backend/main.py#L555)), i.e. protected only by key obscurity. This is accepted for shared images. It is recorded here as a conscious decision that images attached to private recipes carry the same, obscurity-only protection. |
| PRV-6 | The share page **MUST NOT** set analytics, tracking, or session cookies for unauthenticated visitors. |
| PRV-7 | The share endpoint **MUST NOT** allow an address typed by a sharer to be confirmed as an existing account through differences in response body, status code, or timing. |
| PRV-8 | The share page **MUST NOT** disclose how many people the recipe has been shared with, or whether anyone else has opened it. |

---

## 11. Data Model Requirements

Stated as required fields and constraints, not as a schema script.

### 11.1 `User` — new fields

`username` (non-null, unique case-insensitively), `username_changed_at` (nullable).

### 11.2 `Recipe` — new fields

`visibility` (non-null, default `private`), `page_layout` (nullable JSON, always `NULL` in
this release), `page_theme` (nullable JSON, always `NULL` in this release), `copy_count`
(non-null, default 0), `source_recipe_id` (nullable FK, `ON DELETE SET NULL`),
`source_user_id` (nullable FK, `ON DELETE SET NULL`), `source_author_username` (nullable
snapshot), `source_recipe_title` (nullable snapshot), `copied_at` (nullable).

### 11.3 New tables

- **`recipe_shares`** — id, recipe_id, created_by_user_id, token_hash (unique), mode,
  recipient_user_id (nullable), recipient_email (nullable), created_at, expires_at
  (nullable), revoked_at (nullable), last_viewed_at (nullable),
  dismissed_by_recipient_at (nullable). Constraint: `mode = 'person'` requires a recipient.
- **`reserved_usernames`** — username, reason (`system` | `released`), reserved_until
  (nullable; `NULL` means permanent).

### 11.4 Constraints on the change

| ID | Requirement |
|---|---|
| DM-1 | These are schema changes, and the project has no migration system — the schema is created by `Base.metadata.create_all` on startup. `backend/scripts/seed_testing_data.py` **MUST** be updated in the same change so it seeds coherent, valid data for every new column and table: users with unique usernames, recipes at `private` and `unlisted`, at least one active share of each mode, at least one expired share, at least one revoked share, and at least one copy carrying attribution. This is mandatory per `CLAUDE.md`; the change is not complete until the seed script inserts valid data. |
| DM-2 | New backend code outside the `flake8`-excluded directories **MUST** lint clean at the project's 120-character limit. |
| DM-3 | New routes **MUST NOT** be added under the deprecated `/plan` paths. |

---

## 12. Non-Functional Requirements

| ID | Requirement |
|---|---|
| NF-1 | A share page **MUST** render server-side in under 300 ms at p95 for a recipe with 20 ingredients and 15 steps. |
| NF-2 | Share page rendering **MUST NOT** issue N+1 queries for ingredients, tags, or author data. |
| NF-3 | All new unauthenticated endpoints **MUST** be rate-limited, reusing the mechanism introduced with the auth hardening. |
| NF-4 | The share page **MUST** meet WCAG 2.1 AA for contrast, focus visibility, and keyboard navigation. |
| NF-5 | Every requirement in this document describing observable behaviour **MUST** be covered by automated tests, developed test-first per `CLAUDE.md`. |

---

## 13. Acceptance Criteria

This part is complete when all of the following hold:

1. A new local sign-up requires a unique handle; a reserved or taken handle is rejected with
   a clear message; a Google sign-in without a handle is forced to choose one before
   reaching the app.
2. A user opens a private recipe's modal, creates a `link`-mode share, and receives a URL.
   The recipe becomes `unlisted`.
3. That URL, opened in a signed-out browser with JavaScript disabled, renders the complete
   recipe. Pasted into WhatsApp, it unfurls with the recipe's title and image. Its HTML
   contains `noindex`, no structured data, and no canonical link.
4. The share dialog states plainly that anyone holding a `link`-mode URL can open it.
5. A `person`-mode share to another account appears in that account's "Shared with me".
   A signed-out visitor to the same URL is prompted to sign in; a different signed-in
   account receives 403 with the recipient's address masked.
6. The recipient copies the recipe. The copy is private, owned by them, freely editable, has
   its own ingredient and tag rows in their namespace, carries no planner history, and does
   not appear in the planner's candidate pool until copied.
7. The copy displays "Adapted from … by @…". No UI control, API field, or sequence of edits
   removes it. Deleting the source recipe leaves the credit intact.
8. The source's owner sees "copied 1 time" and cannot see who copied it.
9. The owner revokes the share; the recipe returns to `private`; the URL returns a neutral
   404 that does not reveal whether the token ever existed.
10. An attempt to set any recipe to `public` through the API is rejected with 400.
11. A test asserts the public serialiser emits exactly the PRV-2 allowlist and nothing else.
12. A test asserts no route in the release lacks `noindex`, and that no sitemap,
    profile, search, or rating endpoint exists.
13. `scripts/seed_testing_data.py` runs to completion against a fresh database and produces
    data exercising every state above.
14. `flake8 .` and `pytest` pass from `backend/`; `npm run lint` and `npm run test` pass
    from `frontend-v2/`.

---

## 14. Open Questions

| # | Question | Why it matters |
|---|---|---|
| Q-1 | What origin will serve share links? | Share URLs are forwarded and persist in chat history; changing the origin later breaks links people already sent. Needed before the first share is generated in production. |
| Q-2 | Should share links expire by default, and after how long? | SH-9 makes expiry optional. A default expiry limits the blast radius of a forwarded `link`-mode URL, at the cost of links quietly dying in someone's chat history. |
| Q-3 | Are share pages Italian, English, or both? | Determines page copy and the language of the recipient-facing sign-up prompt. Part 2 additionally depends on this for search configuration. |
| Q-4 | Should an image be required before a recipe can be shared? | A share with no image unfurls as a bare text card in WhatsApp. Requiring one is a real quality lever, at the cost of friction. |

---

## 15. Relationship to Part 2

Part 2 covers public visibility and indexable recipe pages, public profile pages at
`/@{username}`, cross-user search, ratings, the page-layout editor, and everything
moderation demands: content screening, reporting, and administrative takedown. It also
carries the non-engineering prerequisites — terms of service, privacy policy, and a
takedown contact.

Part 2 is not scheduled. The purpose of §9 is that it need not be, and that shipping this
part costs nothing and forecloses nothing.
