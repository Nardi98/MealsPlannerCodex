# Requirements — Part 2: Public Publishing & Social Discovery

**Status**: Draft. **Deferred — not scheduled for implementation.**
**Date**: 2026-08-19
**Depends on**: [Part 1 — User-to-User Recipe Sharing](2026-08-19-recipe-sharing-part1-user-to-user.md),
which **MUST** ship first.

Requirement keywords: **MUST** = mandatory. **MUST NOT** = prohibited. **SHOULD** =
strongly recommended, deviation requires written justification. **MAY** = optional.

---

## 1. Context

### 1.1 Why this is separate and deferred

Part 1 lets a user send a recipe to a specific person over a private, `noindex` link. That
creates no public surface and therefore no obligation to police one.

This part is different in kind, not degree. The moment a user can publish a recipe to an
indexable URL on our domain, the project acquires standing obligations: to moderate content
published under our name, to receive and act on reports and takedown demands, to carry
terms of service and a privacy policy, and to handle the reputational consequences of
whatever a stranger decides to publish. Those obligations are ongoing and cannot be
switched off once search engines have indexed the pages.

This document exists so that decision can be taken deliberately, when the project is ready
to carry it — and so that Part 1 can be built with full knowledge of where it is heading,
without committing to arriving there.

### 1.2 Preconditions

This part **MUST NOT** begin until all of the following are true:

| ID | Precondition |
|---|---|
| PRE-1 | Part 1 has shipped and its forward-compatibility requirements (Part 1 §9) are satisfied and tested. |
| PRE-2 | Terms of service, a privacy policy, and a published takedown/abuse contact exist. |
| PRE-3 | A named person is accountable for acting on abuse reports, with a stated response-time expectation. |
| PRE-4 | The hosting origin (Part 1 Q-1) and content language (Part 1 Q-3) are decided and stable. |
| PRE-5 | An explicit, recorded decision has been taken to accept the moderation obligation described in §1.1. |

### 1.3 Objectives

| # | Objective |
|---|---|
| O-1 | A user can publish a recipe to the open web, where it has its own indexable page that search engines surface and social platforms unfurl. |
| O-2 | A user is discoverable as a person through a unique handle and a public profile listing their public recipes. |
| O-3 | Users can find people and public recipes through a search bar in the application. |
| O-4 | Public recipes can be rated, producing an aggregate visible on the page and in search-engine rich results. |
| O-5 | A user can eventually customise the appearance of their own public recipe pages within safe bounds. |
| O-6 | Published content is screened, reportable, and removable, and no public surface leaks private data. |

### 1.4 Non-objectives

- Text reviews or comments.
- Following users, activity feeds, notifications, direct messaging, or any social graph.
- Collaborative editing or shared ownership of a recipe.
- Publishing meal plans, shopping lists, ingredients, or tags. **Only recipes are publishable.**
- User-authored HTML, CSS, or JavaScript (permanently excluded — Part 1 SP-11).
- Automated machine-learning content classification, or an appeals workflow.
- Monetisation or advertising.

### 1.5 Inherited from Part 1

Carried forward unchanged and **MUST NOT** be re-specified or reworked: the block renderer
(P1 RA-6), the public stylesheet (P1 RA-5), the three-state `visibility` field (P1 VIS-1),
the `page_layout` and `page_theme` fields (P1 FC-3, FC-4), the share model and "Shared with
me" (P1 §5), copying and permanent attribution (P1 §7), unique usernames (P1 §8), and the
allowlist public serialiser (P1 PRV-1).

---

## 2. Publishing Requirements

| ID | Requirement |
|---|---|
| PUB-1 | The guard forbidding `visibility = public` (P1 VIS-5) **MUST** be removed, and only that guard — the field itself requires no change. |
| PUB-2 | A `public` recipe **MUST** be reachable at `/r/{slug}`, listed on its owner's profile, included in search results and in `sitemap.xml`, and indexable. |
| PUB-3 | Only the owner, or an administrator under MOD-6, **MUST** be able to change a recipe's visibility. |
| PUB-4 | A recipe **MUST NOT** be publishable if it has no title, no ingredients, or no procedure, or if it fails pre-publish screening (SAF-1). |
| PUB-5 | Demoting `public` → `unlisted` or `private` **MUST** take effect immediately: removal from the profile, from search, and from the next `sitemap.xml` generation. |
| PUB-6 | Publishing and unpublishing **MUST** be rate-limited per user, to prevent sitemap thrash and index churn. |
| PUB-7 | The first transition to `public` **MUST** set `published_at`; subsequent republishing **MUST NOT** change it. |
| PUB-8 | The publish action **MUST** present the user with a plain-language summary of what publishing means — a public page, indexable by search engines, showing their handle — and require explicit confirmation the first time. |

---

## 3. URL Requirements

| ID | Requirement |
|---|---|
| URL-1 | The system **MUST** serve `GET /r/{slug}` — the public recipe page. |
| URL-2 | The system **MUST** serve `GET /@{username}` — the public profile page. |
| URL-3 | The system **MUST** serve `GET /sitemap.xml`, listing every public recipe URL and every profile with at least one public recipe, each with `lastmod` derived from `published_at`. |
| URL-4 | The system **MUST** serve `GET /robots.txt`, permitting `/r/` and `/@`, and disallowing `/s/` and all authenticated API paths. |
| URL-5 | `slug` **MUST** be globally unique, and **MUST** be immutable once the recipe has been public at least once. Editing a recipe's title **MUST NOT** change an existing slug. |
| URL-6 | `slug` **MUST** take the form `{slugified-title}-{short-random-suffix}`, where the suffix guarantees uniqueness without exposing the numeric recipe id. |
| URL-7 | `/r/{slug}` for a recipe no longer public **MUST** return HTTP **410 Gone** with a human-readable page — not 404, and not a redirect. A slug that never existed **MUST** return 404. |
| URL-8 | Re-publishing a previously public recipe **MUST** reuse its original slug. |
| URL-9 | Every root route segment **MUST** already be present in the reserved-username list (P1 UN-4), so `/@{username}` can never collide with a system route. |
| URL-10 | Public pages **MUST** be reachable without authentication and **MUST NOT** require a session cookie to render. |

**Rationale for URL-7**: 410 tells search engines the resource is intentionally gone and
removes it from the index promptly; 404 is treated as possibly transient and lingers. This
matters directly to a user who unpublishes something they regret.

---

## 4. SEO and Structured Data Requirements

| ID | Requirement |
|---|---|
| SEO-1 | Every public recipe page **MUST** embed valid JSON-LD of type `schema.org/Recipe`, containing at minimum `name`, `author` (a `Person` with `name` and a `url` pointing at the profile), `recipeIngredient`, `recipeInstructions` as an ordered list of `HowToStep`, `recipeYield`, `datePublished`, and `image` where one exists. |
| SEO-2 | `aggregateRating` **MUST** be emitted only when `rating_count >= 1`, and **MUST** be omitted entirely otherwise. |
| SEO-3 | Emitted JSON-LD **MUST** validate against the Google Rich Results test for the Recipe type. An automated test **MUST** assert it parses and contains the required keys. |
| SEO-4 | Every public page **MUST** emit OpenGraph and Twitter card tags sufficient to unfurl correctly in WhatsApp, Telegram, and Facebook. |
| SEO-5 | Every public page **MUST** declare `<link rel="canonical">` pointing at its own absolute URL. |
| SEO-6 | For a copied recipe, the canonical **MUST** point at the copy's own URL, and the page **MUST** carry a visible, crawlable attribution link to the source, so the two pages are related rather than competing as duplicates. |
| SEO-7 | Each public page **MUST** have exactly one `<h1>`, use semantic sectioning elements, and provide meaningful `alt` text on every image. |
| SEO-8 | All user-supplied outbound links **MUST** carry `rel="nofollow ugc"`. |
| SEO-9 | `sitemap.xml` **MUST** reflect visibility changes within one generation cycle, and **MUST NOT** list any non-public URL. |
| SEO-10 | Public pages **SHOULD** achieve a Lighthouse SEO score of 100 and a mobile performance score of at least 90. |
| SEO-11 | JSON-LD **MUST** be generated from the same allowlist serialiser as the page body (P1 PRV-1), never from the ORM object directly. |

**Rationale for SEO-2**: an `aggregateRating` with a zero count is a structured-data
validation error and can suppress rich results across the whole domain, not just on the
offending page.

**Rationale for SEO-11**: structured data is the likeliest place for a private field to
leak, because it is machine-readable, invisible in the rendered page, and easy to populate
by spreading an ORM object.

---

## 5. Public Recipe Page Requirements

| ID | Requirement |
|---|---|
| PG-1 | The public recipe page **MUST** render, in the default order: hero (image, title, author, rating), ingredients with quantities and units, steps, attribution where the recipe is a copy, author card, and a report control. |
| PG-2 | The page **MUST** display the author's display name and `@username`, linking to `/@{username}`. |
| PG-3 | The page **MUST** display a servings figure, and **SHOULD** offer client-side ingredient scaling degrading gracefully without JavaScript. |
| PG-4 | The page **MUST** display the aggregate rating and count when `rating_count >= 1`, and a neutral "not yet rated" state otherwise. |
| PG-5 | The page **MUST** offer "Add to my recipe book", prompting sign-in when unauthenticated. |
| PG-6 | The page **MUST** offer a "Report" control (MOD-1). |
| PG-7 | Every public recipe **MUST** be reachable from the authenticated recipe modal in the SPA, through a visible link to its public page. |
| PG-8 | The page **MUST NOT** expose any other recipe of the owner's that is not itself public. |
| PG-9 | The page **MUST** be rendered by the block renderer inherited from Part 1 (P1 RA-6). No second renderer **MUST** be introduced. |

---

## 6. Page Customisation Requirements

This is the last capability to build. It **MUST NOT** precede moderation (§10).

| ID | Requirement |
|---|---|
| CU-1 | `page_layout` (P1 FC-3) **MUST** hold an ordered list of typed blocks. `NULL` **MUST** continue to mean "render the default layout of PG-1". |
| CU-2 | The block type set **MUST** be closed and typed. The initial set is `hero`, `intro_text`, `ingredients`, `steps`, `image`, `gallery`, `tip_callout`, `video_embed`, `author_card`. (`notes` struck: Part 1 removed it from SP-1/PRV-2 because `Recipe` has no `notes` column; Part 2 would have to add one first.) |
| CU-3 | `ingredients` and `steps` blocks **MUST** be present in every valid layout and **MUST NOT** be removable, so a recipe page always contains a recipe. |
| CU-4 | `page_theme` (P1 FC-4) **MUST** hold an accent colour constrained to a defined palette (not free-form hex), a typography preset from a fixed set, a light/dark preference, and hero crop parameters. |
| CU-5 | The system **MUST NOT** accept, store, or render user-supplied HTML, CSS, or JavaScript. This is permanent, not deferred. |
| CU-6 | All user rich text **MUST** be rendered through the strict sanitiser allowlist inherited from Part 1 (P1 SP-10). |
| CU-7 | `video_embed` **MUST** accept only URLs matching a fixed provider allowlist (initially YouTube) and **MUST** render through a privacy-preserving embed. |
| CU-8 | An invalid or unparseable `page_layout` **MUST** fall back to the default layout rather than raising, so a malformed write can never take a public page offline. |
| CU-9 | A layout edit **MUST** be previewable before it is saved. |
| CU-10 | Customisation **MUST NOT** be able to remove or obscure the attribution line (P1 AT-4) or the report control (PG-6). |

**Rationale for CU-5**: arbitrary user CSS and JavaScript would be a cross-site-scripting
vector, would let a user break the page's crawlability and accessibility, would defeat the
design system, and would create an unbounded support surface. Any future "custom styling"
is a whitelisted token set, never a stylesheet.

---

## 7. Public Profile Requirements

| ID | Requirement |
|---|---|
| PR-1 | `/@{username}` **MUST** render the avatar, display name, `@username`, bio, join month, count of public recipes, and a grid of that user's **public recipes only**. |
| PR-2 | The profile **MUST NOT** display or expose an email address, a numeric user id, plan settings, `default_people`, any private or unlisted recipe, or any figure revealing how many non-public recipes exist. |
| PR-3 | The profile **MUST** offer sorting by newest and by top-rated. |
| PR-4 | The profile **MUST** paginate for users with many public recipes, using crawlable pagination links — not infinite scroll alone. |
| PR-5 | `User` **MUST** gain a `bio` field: plain text, maximum 300 characters, sanitised, with URLs rendered `nofollow ugc`. |
| PR-6 | `User` **MUST** gain an `avatar_url` field. Avatar upload **MUST** reuse the existing image storage path (`storage.save_image`) with the same content-type and size limits already applied to recipe images. |
| PR-7 | A profile with zero public recipes **MUST** still render, with an empty state, but **MUST NOT** appear in `sitemap.xml`. |
| PR-8 | A suspended user's profile (MOD-6) **MUST** return 404, and all their public recipe pages **MUST** return 410. |
| PR-9 | The username handle, displayed as plain text in Part 1 (P1 UN-10), **MUST** become a link to the profile. |
| PR-10 | Changing a username **MUST NOT** redirect the old handle to the new profile; during its reservation window (P1 UN-9) the old handle **MUST** return 404. |

**Rationale for PR-10**: a redirect would let someone release a handle, have a third party
claim it, and continue to receive that person's traffic — or the reverse. A hard 404 during
the reservation window makes handle identity unambiguous.

---

## 8. Search Requirements

| ID | Requirement |
|---|---|
| SR-1 | A search endpoint **MUST** return results grouped into *People* and *Recipes*. |
| SR-2 | Recipe search **MUST** match against title (highest weight), tag names, and ingredient names (lowest weight). |
| SR-3 | People search **MUST** match against `username` and `display_name`. |
| SR-4 | Recipe search **MUST** return only recipes whose `visibility` is `public`, enforced in the query rather than in the template. An automated test **MUST** assert that private and unlisted recipes are unreachable through search. |
| SR-5 | Search **MUST** be implemented with PostgreSQL full-text search. No external search service **MUST** be introduced. |
| SR-6 | Search **MUST** be available unauthenticated and **MUST** be rate-limited by IP. |
| SR-7 | Search results **MUST NOT** expose any field outside the public allowlist. |
| SR-8 | Search **MUST** tolerate accents and diacritics, so that "purè" and "pure" match. |
| SR-9 | Search **MUST NOT** return suspended users or their recipes. |
| SR-10 | The search bar **MUST** be reachable from the application's top-level navigation. |

---

## 9. Rating Requirements

| ID | Requirement |
|---|---|
| RT-1 | A rating **MUST** be an integer from 1 to 5 inclusive, enforced by a database `CHECK` constraint. |
| RT-2 | Rating **MUST** require authentication. Anonymous rating **MUST NOT** be possible. |
| RT-3 | A user **MUST** have at most one rating per recipe, enforced by a composite primary key or unique constraint on `(recipe_id, user_id)`. |
| RT-4 | Re-rating **MUST** update the existing rating in place, never create a second. |
| RT-5 | A user **MUST** be able to delete their own rating, decrementing the aggregate accordingly. |
| RT-6 | The owner of a recipe **MUST NOT** be able to rate it. |
| RT-7 | Only `public` recipes **MUST** be rateable. Rating an unlisted or private recipe **MUST** be rejected. |
| RT-8 | Aggregates **MUST** be maintained as denormalised `rating_sum` and `rating_count` columns on `Recipe`, written in the same transaction as the rating, so page rendering and search ranking never aggregate at read time. |
| RT-9 | The displayed rating **MUST** be the mean to one decimal place, accompanied by the count. |
| RT-10 | If a recipe leaves `public`, existing ratings **MUST** be retained and restored on re-publication. |
| RT-11 | Rating **MUST** be rate-limited per user. |
| RT-12 | Raters' identities **MUST NOT** be exposed to the recipe owner or to anyone else. |
| RT-13 | Free-text reviews **MUST NOT** be part of this scope. |

---

## 10. Safety and Moderation Requirements

Nothing in §2–§9 may ship before this section does. Publishing without a removal path is
the specific risk this whole split exists to avoid.

### 10.1 Pre-publish screening

| ID | Requirement |
|---|---|
| SAF-1 | A profanity and hate-term screen **MUST** run on every transition to `public`, on every edit to an already-public recipe, and on every change to a `bio` or `username`. It **MUST** cover title, procedure, and all user text blocks. |
| SAF-2 | The screen **MUST** be free and offline, requiring no third-party API, network call, or API key. |
| SAF-3 | The screen **MUST** cover both English and Italian terms. |
| SAF-4 | The screen **MUST** normalise common evasions — leetspeak substitutions, repeated characters, inserted separators — before matching. |
| SAF-5 | On a match, publishing **MUST** be refused with a clear message naming the matched term so the user can correct it. The content **MUST** remain saved as private or unlisted; nothing is deleted. |
| SAF-6 | The screen **MUST NOT** run on `private` or `unlisted` content. A user's own private notes are never screened. |
| SAF-7 | The term list **MUST** be a committed, reviewable file, amendable without changing matching logic. |
| SAF-8 | The screen is explicitly **not required to be exhaustive or reliable**. Its purpose is to keep obvious cases from ever obtaining an indexable URL and to reduce report volume. False negatives are handled by reporting. |
| SAF-9 | A user whose publication is blocked **MUST** be able to request human review. |

### 10.2 Reporting and administration

| ID | Requirement |
|---|---|
| MOD-1 | Every public recipe page and public profile **MUST** carry a "Report" control. |
| MOD-2 | Reporting **MUST** be possible without authentication, and **MUST** be rate-limited by IP. |
| MOD-3 | A report **MUST** record target type, target id, a reason from a fixed enum, an optional free-text note, the reporter's user id when authenticated, a timestamp, and the originating IP. |
| MOD-4 | Report submission **MUST** notify the administrator by email, via the existing [mailer.py](../../../backend/mailer.py). |
| MOD-5 | `User` **MUST** gain an `is_admin` flag. |
| MOD-6 | An administrator **MUST** be able to (a) force-unpublish any recipe, setting it to `private` so its slug returns 410, and (b) suspend a user, taking their profile and all their public recipes offline per PR-8. |
| MOD-7 | Administrative actions **MUST** be recorded with actor, target, action, and timestamp. |
| MOD-8 | Suspension **MUST** be reversible and **MUST NOT** delete user data. |
| MOD-9 | A takedown path **MUST** be reachable by a non-user — someone who believes their content was published by another — without requiring an account. |
| MOD-10 | A moderation queue UI **MUST NOT** be built in this scope. Email notification plus direct administrative action is sufficient until report volume justifies more. |

---

## 11. Privacy Requirements

| ID | Requirement |
|---|---|
| PRV-1 | Public responses and pages **MUST** continue to be serialised through the allowlist schema inherited from Part 1, extended — not restructured — with the fields this part adds. |
| PRV-2 | Fields added to the allowlist by this part: slug, published date, aggregate rating and count, copy count, author avatar, author bio. |
| PRV-3 | The prohibitions of Part 1 PRV-3 **MUST** continue to hold, extended with: the identities of raters, the identities of copiers, and any indication of how many non-public recipes a user owns. |
| PRV-4 | The test asserting the emitted field set **equals** the allowlist (P1 PRV-4) **MUST** be extended to cover the public recipe page, the profile page, search results, and JSON-LD independently. |
| PRV-5 | Public pages **MUST NOT** set analytics, tracking, or session cookies for unauthenticated visitors. |
| PRV-6 | Publishing **MUST** be reversible in the sense the user expects: unpublishing must remove the page from our serving and from the sitemap promptly. It **MUST** be stated plainly at PUB-8 that we cannot remove copies already made by search engines or other users. |

---

## 12. Data Model Requirements

Additive to the Part 1 model.

### 12.1 `User` — new fields

`bio` (nullable, ≤300 characters), `avatar_url` (nullable), `is_admin` (non-null, default
false), `suspended_at` (nullable).

### 12.2 `Recipe` — new fields

`slug` (unique, nullable until first publication, immutable thereafter), `published_at`
(nullable), `rating_sum` (non-null, default 0), `rating_count` (non-null, default 0).

`visibility`, `page_layout`, `page_theme`, `copy_count`, and the attribution snapshot
columns already exist from Part 1 and **MUST NOT** be altered.

### 12.3 New tables

- **`recipe_ratings`** — recipe_id, user_id, stars (CHECK 1–5), created_at, updated_at;
  primary key `(recipe_id, user_id)`.
- **`reports`** — id, target_type, target_id, reason, note (nullable), reporter_user_id
  (nullable), reporter_ip, created_at, resolved_at (nullable), resolution_note (nullable).
- **`admin_actions`** — id, actor_user_id, action, target_type, target_id, created_at, note.

### 12.4 Constraints on the change

| ID | Requirement |
|---|---|
| DM-1 | `backend/scripts/seed_testing_data.py` **MUST** be updated in the same change to seed coherent data for every new column and table, including public recipes with slugs, ratings, a copied-and-republished recipe, an administrator account, and a suspended account. Mandatory per `CLAUDE.md`. |
| DM-2 | New backend code outside the `flake8`-excluded directories **MUST** lint clean at the 120-character limit. |
| DM-3 | This part **MUST NOT** alter any column, route, or template shipped by Part 1 other than removing the guard of PUB-1 and linking the handle per PR-9. Any need to do otherwise indicates a defect in Part 1's forward-compatibility requirements and **MUST** be recorded as such. |

---

## 13. Non-Functional Requirements

| ID | Requirement |
|---|---|
| NF-1 | A public recipe page **MUST** render server-side in under 300 ms at p95 for a recipe with 20 ingredients and 15 steps. |
| NF-2 | Public page rendering **MUST NOT** issue N+1 queries for ingredients, tags, author data, or ratings. |
| NF-3 | `sitemap.xml` **MUST** remain correct and servable at 50,000 public recipes, paginating into a sitemap index as that limit is approached. |
| NF-4 | All new public endpoints **MUST** be rate-limited. |
| NF-5 | Public pages **MUST** meet WCAG 2.1 AA for contrast, focus visibility, and keyboard navigation. |
| NF-6 | Public pages **MUST** follow `MEAL_PLANNER_DESIGN_GUIDE.md`. |
| NF-7 | Every requirement describing observable behaviour **MUST** be covered by automated tests, developed test-first per `CLAUDE.md`. |

---

## 14. Acceptance Criteria

1. A user publishes a recipe; `/r/{slug}` returns complete HTML with valid Recipe JSON-LD;
   the URL unfurls with image and title in WhatsApp; the page appears in `sitemap.xml`; the
   page is fully readable with JavaScript disabled.
2. The recipe appears on `/@{username}`, which itself renders and is indexable.
3. A private and an unlisted recipe are unreachable through `/r/`, the profile, the
   sitemap, and search — asserted by test.
4. A second user finds the first by handle in the search bar, opens their profile, opens a
   public recipe, and copies it. The copy carries the non-removable attribution from Part 1.
5. The second user publishes their copy; the attribution link is present and crawlable, and
   the copy's canonical points at itself.
6. A third user rates the copy 4 stars; the page shows 4.0 (1) and `aggregateRating` appears
   in JSON-LD. The owner cannot rate their own recipe. A repeat rating updates rather than
   duplicates. With zero ratings, `aggregateRating` is absent entirely.
7. Publishing a recipe whose title contains a blocklisted term is refused with a message
   naming the term; the recipe remains saved and unpublished.
8. An anonymous visitor reports a public recipe; the administrator receives an email and
   force-unpublishes it; the slug thereafter returns 410 and it leaves the sitemap.
9. An administrator suspends a user; their profile returns 404, their public recipes return
   410, and neither appears in search.
10. Unpublishing a recipe returns 410 for its slug and removes it from the next sitemap.
11. Tests assert the emitted field set equals the allowlist independently for the recipe
    page, the profile page, search results, and JSON-LD.
12. `scripts/seed_testing_data.py` runs to completion against a fresh database and produces
    data exercising every state above.
13. `flake8 .` and `pytest` pass from `backend/`; `npm run lint` and `npm run test` pass
    from `frontend-v2/`.

---

## 15. Sequencing Within This Part

If this part is ever undertaken, moderation is not the last step. The order **MUST** be:

1. **Safety first** (§10) — screening, reporting, administrative unpublish and suspend.
   Built and tested before any page is publicly reachable.
2. **Public rendering** (§2–§5) — slugs, `/r/{slug}`, JSON-LD, sitemap, robots.
3. **Profiles** (§7).
4. **Search** (§8).
5. **Ratings** (§9).
6. **Page customisation** (§6) — last, and only once everything above is stable.

Building moderation after publishing would mean a window in which content is indexable and
irremovable. That window is exactly the risk this document exists to prevent.

---

## 16. Open Questions

| # | Question | Why it matters |
|---|---|---|
| Q-1 | Are public pages Italian, English, or both with `hreflang`? | Determines JSON-LD `inLanguage`, page copy, the profanity term list, and the PostgreSQL full-text search configuration. |
| Q-2 | Should an image be mandatory before publication? | Recipe rich results and social unfurls are substantially weaker without one. A real quality lever, at the cost of friction. |
| Q-3 | Should "copied N times" be public, or visible only to the owner? | Currently specified as owner-only in Part 1 (P1 AT-7); making it public is a mild social-proof signal with mild pressure attached. |
| Q-4 | What response-time commitment applies to abuse reports? | PRE-3 requires one to exist. It also determines whether email notification alone remains sufficient (MOD-10). |
| Q-5 | Should publishing require a verified email address? | Raises the cost of throwaway-account abuse considerably, at the cost of blocking some legitimate users. |
