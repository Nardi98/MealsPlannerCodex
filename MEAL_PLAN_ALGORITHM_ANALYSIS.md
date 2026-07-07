# Weekly Meal Plan Algorithm — Analysis

*Generated analysis of how `mealplanner` builds a weekly plan. Source of truth:
`backend/mealplanner/planner.py`, `backend/mealplanner/scoring.py`,
`backend/mealplanner/config.py`, plus the `crud`/`main` feedback loop.*

## 1. High-level overview

The planner is a **greedy, slot-by-slot scorer with ε-greedy exploration and a
"soft-hold" leftover scheduler**. It does not optimize the week globally; it
walks each meal slot in chronological order, scores every eligible recipe for
that slot, and picks the best (or, with probability ε, a random one).

The pipeline for a generate request (`generate_plan` in `planner.py:54`):

1. **Build the candidate pool** — load all `main` / `first-course` recipes with
   ingredients + tags eagerly joined (`planner.py:81`). `side` recipes are
   handled separately by `generate_side_dish`.
2. **Load recency data** — the most recent non-leftover `plan_date` per recipe
   from the `meals` table (`planner.py:91`).
3. **Build empty slots** — one `Slot` per `(day, meal_number)` for `days ×
   meals_per_day` (`planner.py:98`).
4. **Iterate slots in order.** For each slot:
   - Refresh leftover **soft holds** for future slots (`_apply_soft_holds`).
   - **Filter** recipes by season + tags for that slot's date.
   - **Score** every surviving recipe.
   - **Select** best (exploit) or random (explore, prob ε).
   - Update recency + register leftovers if the chosen recipe is `bulk_prep`.

## 2. Filtering (`filter_recipes`, `planner.py:307`)

Applied fresh for every slot because the season depends on the slot's month:

- **`avoid_tags`** — recipe dropped if it has *any* avoid tag.
- **`tags`** (include) — recipe kept only if it has *at least one* include tag.
- **`season`** — recipe kept only if *at least one* ingredient is in season for
  the slot's month. An ingredient with an empty `season_months` is treated as
  available year-round. Recipes with no ingredients bypass the season check.
- **`reduce_tags`** — matching recipes are not dropped; they are pushed to the
  **end** of the list (`primary + reduced`). This only matters for tie-breaking
  order, since selection is score-based (see the tag *penalty* below for the
  real de-prioritization).

If the pool is empty for a slot, generation raises `ValueError("No recipes
available")`.

## 3. Scoring (`score_recipe`, `scoring.py:152`)

The final score is a sum of five weighted components:

```
score = base
      + seasonality_weight * seasonality_bonus
      + recency_weight     * recency_penalty
      + bulk_bonus_weight  * bulk_bonus
      + tag_penalty_weight * tag_penalty
```

### Base score (normalized + squashed)
The raw `recipe.score` (nudged by user feedback, §5) is **normalized against the
current candidate pool** and squashed with `tanh` into `[-B, B]` (default
`B=3`). Two modes:

- **`zscore`** (default): `(raw − mean) / std` over the pool's base scores.
- **`percentile`**: maps rank to `[-1, 1]`.

Result: `base = B · tanh(k · norm)`. Squashing means one recipe with a runaway
score can't dominate — its base contribution is capped at ±3, which is small
relative to the other components (seasonality ±10, recency up to −30).

### Seasonality (`seasonality_bonus`, `scoring.py:79`)
Each ingredient with *meaningful* seasonal data (`0 < len(season_months) < 12`)
votes `+1` if the slot's month is in season, `−1` otherwise. Ingredients with no
data or all-year availability are neutral. Net vote is averaged over **all**
ingredients and scaled by `SEASONALITY_BONUS_SCALE = 10`. Fully in-season → +10,
fully out-of-season → −10.

### Recency (`recency_penalty`, `scoring.py:50`)
A **negative** penalty for recently-planned recipes, based on days since
`date_last_planned`:

- Planned in the future relative to this slot (`days < 0`) → **0** (not consumed
  yet).
- Same day (`days == 0`) → **−30** (`RECENCY_MAX_PENALTY`).
- `days ≥ 15` (`RECENCY_WINDOW_DAYS`) → **0**.
- Between → exponential decay with a **4-day half-life** (`HALF_LIFE_DAYS`):
  `−30 · exp(−ln2 · days / 4)`.

This is the dominant "don't repeat things" force and is what drives variety
across the week (each pick updates `last_planned`, penalizing the recipe for the
next ~2 weeks of slots).

### Bulk bonus (`bulk_bonus`, `scoring.py:121`)
Flat `+10` (`BULK_PREP_BONUS`) if `recipe.bulk_prep` is set — nudges the plan
toward batch-cookable meals (which then feed the leftover system).

### Tag penalty (`tag_penalty`, `scoring.py:127`)
Flat `−3` (`DEFAULT_TAG_PENALTY`) if the recipe carries any `reduce_tags`. This
is the real de-prioritization mechanism for reduce tags (the filter reorder is
cosmetic).

## 4. Selection & leftover "soft holds"

### ε-greedy selection (`planner.py:139`)
Candidates are sorted by score descending. With probability **ε** a random
candidate is chosen (`selection_mode = "explore"`); otherwise the top candidate
(`"exploit"`). ε is caller-supplied and defaults to `0.0` (pure greedy). This is
the exploration lever that lets the planner occasionally surface recipes the
score would otherwise bury.

### Soft-hold leftover scheduling (`_apply_soft_holds`, `planner.py:193`)
When a chosen recipe is `bulk_prep` and `bulk_leftovers` is on, a leftover
record is registered (`planner.py:167`) with:
- `repeats_remaining` — from `LEFTOVER_REPEAT_BY_RECIPE[id]` or
  `LEFTOVER_REPEAT_DEFAULT` (1).
- `window_end` — `source_date + keep_days − 1`.
- `next_date` — earliest reuse date, `source_date + LEFTOVER_SPACING_GAP` (2).

Before each slot, `_apply_soft_holds` re-scans future slots and stamps
`soft_hold_recipe_id` onto eligible ones, respecting:
- `LEFTOVER_SPACING_GAP` (2 days between repeats),
- `MAX_LEFTOVERS_PER_DAY` (2),
- `LEFTOVER_DAYPART_PREF` + `MEAL_NUMBER_TO_DAYPART` (`{1: LUNCH, 2: DINNER}`) —
  a leftover can be pinned to lunch or dinner slots only.

A soft hold biases a slot toward reusing the leftover in two ways
(`planner.py:126–136`):
1. The recipe's **recency penalty is zeroed** in its held slot (so a
   just-cooked recipe isn't penalized for being reused as a leftover).
2. Every *other* recipe gets `−SOFT_HOLD_PENALTY` (1.0), tilting the slot toward
   the held recipe.

It's a *soft* hold: a strongly-scored alternative can still win, in which case
the leftover simply isn't consumed that slot. When a leftover is consumed,
`repeats_remaining` decrements and `next_date` advances; it's removed once
repeats hit zero or the window closes (`planner.py:152`). Leftover meals are
flagged `leftover=True` and surfaced in the API response
(`main.py:471`); the title suffix `" (leftover)"` convention is parsed elsewhere.

## 5. The learning loop (feedback → base score)

The planner is "learning-based" only through the recipe `score` field, adjusted
by user feedback:

- **Accept** (`/feedback/accept` → `crud.accept_recipe`, `crud.py:514`):
  `score += 1` and `date_last_consumed` updated.
- **Reject** (`/feedback/reject` → `crud.reject_recipe`, `crud.py:534`):
  `score −= 1`, and the endpoint suggests a random unused replacement
  (`main.py:433`).

These accumulated scores feed back in as the **base score** on the next
generation, after z-score normalization and tanh squashing. So feedback is a
slow, bounded nudge — it shifts a recipe's relative rank within the pool but
(by design of the squash) can't overpower seasonality/recency.

## 6. Side dishes (`generate_side_dish`, `planner.py:236`)

Separate path: filters `course == "side"` recipes (optionally excluding
`avoid_titles`), scores them with the **same** `score_recipe` using *today's*
date for season/recency, and returns the single best (or random under ε). Recency
here is keyed off `MealSide.plan_date`. No leftover logic.

## 7. Key characteristics & caveats

- **Greedy, not globally optimal.** Order-dependent; an early pick can constrain
  later slots. There's no backtracking.
- **Deterministic when ε = 0** (aside from feedback state), which the codebase
  relies on for unit tests.
- **Component magnitudes are hardcoded** in `scoring.py` (recency −30 dominates,
  base capped at ±3, seasonality ±10, bulk +10, tag −3). Weights scale but don't
  change these ceilings.
- **Recency is the main variety engine**; seasonality shapes *what fits the
  month*; feedback slowly reweights preferences within those constraints.
- Tunables live in `scoring.py` (`RECENCY_*`, `HALF_LIFE_DAYS`, bonuses) and
  `config.py` (`DEFAULT_PLAN_SETTINGS` leftover/daypart parameters).
