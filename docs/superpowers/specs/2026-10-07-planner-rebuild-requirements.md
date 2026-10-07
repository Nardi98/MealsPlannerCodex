# Planner rebuild — requirements

Date: 2026-10-07
Status: approved. Q1–Q11 were closed by the owner on 2026-10-07 (see *Decisions*).
Source: the phase 1 audit (https://claude.ai/artifact/QUEfyCR8NiDtxDkxNQjiE7) and the
owner's triage of its findings.

## Purpose

Repetition, ignored rejections and invisible decisions all come from one structure:
several unrelated ways of picking a recipe, no memory of what was suggested, and no record
of why. This rebuild replaces that structure with **one selection engine that every
picking path goes through** and **a suggestion log** that is both the planner's memory and
its trace.

Revised after triage: the planner's memory lives on `Recipe` (`date_last_suggested`,
`date_last_rejected`); the log is a developer-only trace (FR-22).

## Scope

**Rebuilt:** the selection logic in `mealplanner/planner.py` and `mealplanner/scoring.py`,
the reject-replacement logic in `feedback_reject`, and the side-suggestion logic in
`generate_side_dish`.

**Kept as they are:** the `meals` / `meal_plans` / `meal_sides` tables, plan persistence
(`set_meal_plan`, `_assign_leftover_sources`, `swap_meals`), tenancy and auth, and the
frontend's structure. Frontend calls are repointed where an endpoint changes.

**By design, not to be changed** (owner's triage):

| Finding | Behaviour that stays |
| --- | --- |
| R2 | A single rejection is a mild preference signal, not a hard veto. |
| L2 | Rejecting a bulk source replaces each of its leftover slots independently. |
| L3 | Leftover links are re-derived at save time by `_assign_leftover_sources`. |
| S2 | During generation a side is a random favorite of the main. "Add side" picks a scored side. |
| F1 | Accept bumps the main and every side. A manual swap is a reject of the old dish plus an accept of the new one. |

## Functional requirements

### One engine

- **FR-1** Every path that proposes a recipe uses the same engine: generate week,
  replacement after rejecting a main, add side, and replacement after rejecting a side.
- **FR-2** The engine runs fixed stages in order: *candidates → hard rules → scoring →
  selection*. Each stage can be tested on its own without a database.
- **FR-3** A hard rule removes a candidate. It is never a score adjustment. Hard rules:
  rejection ban (FR-10), avoid-tags, fully out of season, and already on the same plate
  (sides).
- **FR-4** Scoring is a sum of named terms, each with a fixed and documented range. The
  engine returns the breakdown per term, not just the total.

### Variety (R3, R4, R5)

- **FR-5** Selection is unchanged: the top score wins, unless the ε-greedy explore draw
  fires (Q1). Variety comes from the explore draw, the ban and the minimum gap.
- **FR-6** A main eaten within the last **5 days** is a hard exclusion (`min_gap`) (Q2). It
  may break the gap only if it uses a fridge ingredient, or if it is **strictly seasonal**:
  at least one ingredient carries seasonal data and every such ingredient is in season
  this month. Sides get the recency penalty and the ban, but no minimum gap.
- **FR-7** Recency is measured from the most recent meal **on or before** the slot's date.
  A meal planned after the slot never hides an earlier one (R5).

### "Chance to shine" (exploration)

- **FR-8** Exploration affects **only the ε explore draw**. A recipe's draw weight is the
  number of days since it was last **suggested** (`Recipe.date_last_suggested`, rejected
  suggestions included); a never-suggested recipe weighs 365.
- **FR-9** A recipe **kept** on a plan (any `Meal` row) within 7 days of the slot weighs 0
  in the explore draw (Q3). A rejected suggestion has only the ban (FR-10).
- **FR-9a** The explore weight is no longer damped by a negative score, so a season of
  rejections cannot bury a dish (Q4). The −1 preference drop per rejection stays (R2).

### Rejection (R1, S3)

- **FR-10** Rejecting a dish bans it for **4 days**, mains and sides alike (Q5). The ban is
  anchored on the rejected **slot date**: `date_last_rejected = slot date`, and the dish is
  excluded from slots in `[rejected_slot, rejected_slot + 3]`.
- **FR-11** The replacement for a rejected main is the engine's best candidate **for that
  slot** (its date, its meal number, the rest of the plan as context), never a uniform
  random draw.
- **FR-12** Rejecting a side does not compute a main replacement. Each kind of rejection
  has its own path (S3).
- **FR-13** Feedback identifies the recipe **by id**, never by title (F1).

### Leftovers (L1)

- **FR-14** When a bulk-prep recipe is cooked fresh, its leftover slots are **reserved**
  inside the keep window, respecting spacing, the per-day cap and daypart preference. A
  reserved slot is filled by the leftover, not by competing dishes. The held recipe gets a
  visible `hold` term of **+15** (`LEFTOVER_HOLD_MARGIN`, a plan setting) and is exempt on
  that slot from its own recency, ingredient-repeat and tag-repeat penalties. Only a dish
  more than 15 points better takes the slot (Q6). This replaces `SOFT_HOLD_PENALTY`.
- **FR-15** Leftover repeats per recipe and spacing keep their current settings
  (`LEFTOVER_REPEAT_DEFAULT`, `LEFTOVER_REPEAT_BY_RECIPE`, `LEFTOVER_SPACING_GAP`,
  `MAX_LEFTOVERS_PER_DAY`, `LEFTOVER_DAYPART_PREF`).
- **FR-16** Accepting a leftover meal marks it accepted but does **not** bump the score;
  one batch counts as one accept (Q7).

### Sides (S1)

- **FR-17** "Add side" scores against **the meal's date**, not today.
- **FR-18** Repeated "Add side" requests across a week do not all return the same side.
  The same variety rule as FR-5 applies.

### Plan generation range (F3)

- **FR-19** Generation and overwrite accept only ranges starting **today or later**.
  Days already past are never deleted by regeneration. Enforced on the server, mirrored
  in the UI.

### Suggestion log and observability (O1, O2)

- **FR-20** Every proposal the engine makes is recorded: who, when, which path (generate /
  replace-main / add-side / replace-side), target date and meal number, the chosen
  recipe, its rank, its per-term score breakdown, and enough of the runner-up candidates
  to explain the choice.
- **FR-21** The outcome of a proposal is recorded when known: kept, rejected (→ ban),
  replaced by hand, accepted.
- **FR-22** *Rejected as written.* The log is developer-only. Planner state lives on
  `Recipe`: `date_last_suggested` (new) and `date_last_rejected` (now the slot date).
- **FR-23** Log rows older than **90 days** are pruned on write. Each slot stores at most the
  **top 5** runners-up (Q8).
- **FR-24** A run does not have to be replayable. It does have to be **understandable**:
  for any slot you can see why its dish beat the others. It is read from an admin
  **Logs** page that exports a user's log as JSON (Q9, FR-27 to FR-29).

### Cleanup (L4, F2)

- **FR-25** Remove settings and request fields nothing reads: `MAX_LEFTOVERS_PER_WEEK`,
  `LEFTOVER_ACCEPT_WEIGHT`, `LEFTOVER_DAYPART_WEIGHT`, `PROTECT_EXPLORE_SLOTS`,
  `EXPLORE_PROTECTION_COST`, the unused `MealPlanGenerate` fields, and the unused
  `generate_plan` parameters (`min_recipe_gap`, `tags`).
- **FR-26** `Recipe.date_last_consumed` is dropped (Q10): recency already comes from
  `meals`. Import keeps accepting old files that carry the field and ignores it.

### Developer log (`devlog`)

- **FR-27** A generic developer log, `dev_log_entries`: one row per event, owned by a user,
  with a `channel` (an area of the app; `planner` first), an `event` name and a JSON
  `payload`. Writes go through `devlog.record`, which prunes that user's rows older than
  90 days.
- **FR-28** The planner logs `generate` (params, settings, per-slot trace), `replace_main`,
  `suggest_side` and `feedback` events.
- **FR-29** An admin-only **Logs** page searches a user by email or username and downloads
  that user's log as JSON, optionally filtered by channel. The server enforces admin.

## Non-functional requirements

- **NFR-1 Tenancy.** Every new query goes through `scoping.scope()`. The suggestion log is
  owned via `models._owner_fk_column()`.
- **NFR-2 Schema discipline.** Every model change ships with a read and checked Alembic
  revision, named constraints, and an updated `scripts/seed_testing_data.py`, in the same
  commit.
- **NFR-3 TDD.** Implemented test-first (`/test-driven-development`). The engine's stages
  get unit tests without a database. The paths get API tests against the disposable
  Postgres.
- **NFR-4 Determinism in tests.** The engine takes an injected random source. Production
  may be random, tests pass a seed.
- **NFR-5 Boundaries.** The engine module imports no FastAPI and no route module. A guard
  in `tests/test_architecture_guards.py` enforces it.
- **NFR-6 Performance.** Generating a week with two meals a day for a library of a few
  hundred recipes stays under **1 s** server time (14 slots, a few hundred recipes). One
  timing test guards against regressions (Q11).
- **NFR-7 Lint.** `flake8` clean, max line length 120.
- **NFR-8 Last step.** The implementation plan ends with `/simplify`.

## Decisions

| # | Decision |
| --- | --- |
| Q1 | Selection unchanged: argmax, with an ε-greedy explore draw. |
| Q2 | Hard minimum gap of 5 days for mains; fridge or strictly seasonal dishes may break it. Sides: recency and ban only. |
| Q3/Q4 | Exploration affects only the ε draw: weight = days since last suggested (365 if never), 0 if kept within 7 days; no negative-score damping. |
| Q5 | 4-day ban for mains and sides, anchored on the rejected slot date. |
| Q6 | Held slot: `hold` term +15 (`LEFTOVER_HOLD_MARGIN`); the held recipe is exempt from its own repetition terms. |
| Q7 | A leftover accept marks the meal accepted without bumping the score. |
| Q8 | 90-day retention, pruned on write; top 5 runners-up per slot. |
| Q9 | Generic `devlog` plus an admin Logs page with a per-user JSON export. |
| Q10 | Drop `date_last_consumed`. |
| Q11 | Under 1 s for 14 slots over a few hundred recipes; one timing test. |
