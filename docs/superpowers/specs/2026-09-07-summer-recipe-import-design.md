# Summer recipe import file — design

**Date:** 2026-09-07
**Deliverable:** a JSON file for `POST /data/import?mode=merge`, carrying 24 of the 29
recipes from `ricettario-estivo-saziante.md`, plus an audit report of everything inferred.

## Goal

The source document is 29 Mediterranean vegetarian recipes written for September heat, in
Italian, at mixed serving sizes, several with no quantities at all. The account they are
going into already holds 44 recipes and ~70 ingredients in English. The job is to turn the
first into something the second can absorb without producing duplicate pantry rows or a
shopping list that cannot be summed.

## Scope

In: recipes, ingredients, tags. Out: meal plans (the file carries none, so importing it
cannot disturb the current week), and any repair of pre-existing data.

## Decisions

| Question | Decision |
|---|---|
| Delivery | A file the user imports by hand. Nothing writes to the live account. |
| Mode | `merge`. `overwrite` would clear the existing 44 recipes. |
| Coverage | 24 of 29 — five are dishes the account already holds (see *Duplicates*). Every one carries real quantities. |
| Language | English throughout — titles, procedures, ingredient names. |
| Servings | `servings: 4` throughout; source quantities rescaled by 4/portions. |
| Courses | Judged per recipe (see below). |
| Tags | Small functional set, reusing existing tag names where they exist. |
| Inference | Fill `season_months` and the `grams_per_*` conversions; every inferred value listed in the report. |
| Fidelity | The source is not trusted. Quantities that do not hold up are corrected against standard versions, and each correction is recorded. |

### Duplicates

A recipe already in the account is not imported again — a second row for the same dish
splits its score history and gives the planner two candidates it will treat as unrelated.
Five are skipped:

| Source | Existing recipe |
|---|---|
| #3 Hummus with crudités | Classic Hummus (75) |
| #5 Baba ganoush | Babaganoush (76) |
| #11 Baked courgette and onion frittata | Zucchini Frittata (70) |
| #24 Tomato salad with oregano | Tomato and Cucumber Salad (91), and Tomato salad (93) |
| #28 Green salad with lemon vinaigrette | Green Salad (90) |

Four near-misses are kept, being genuinely different dishes: #26 raw courgette ribbons
(against the pan-fried 86), #27 cold roasted peppers (against the stewed Peperonata 79),
#29 confit cherry tomatoes (which exist only as a step inside recipe 40, never standalone),
and #25 quick pickled cucumbers.

### Course assignment

- `first-course` (5) — the two cold soups (gazpacho, chilled courgette velouté) and the
  three grain dishes (farro salad, panzanella, wholewheat couscous).
- `main` (7) — stuffed aubergines, the four phyllo dishes (courgette burek, spanakopita,
  phyllo cigars, krompiruša), aubergine involtini, and the roasted vegetable tray (which
  the source calls a base, but which is a main at 4 portions).
- `side` (12) — four spreads (tzatziki, pepper-and-feta, cannellini, roasted
  courgette-ricotta), four cold vegetable and legume dishes (courgettes in scapece,
  chickpea salad, lentil salad, cannellini with rocket), and four quick sides (pickled
  cucumbers, courgette ribbons, roasted peppers, confit tomatoes).

### Ingredient identity

Import matches an ingredient by `id` first, then by exact `name`, and creates it otherwise
(`crud.get_or_create_ingredient`). So:

- Existing ingredients are referenced **by their existing id and exact name**, and carry
  their existing `season_months` / `grams_per_ml` / `grams_per_piece` / `preferred_dimension`
  unchanged. Conversions are backfilled by import and never overwritten, so supplying them
  is safe.
- New ingredients carry **no `id`** — an invented id would bind to an unrelated row. They
  are: Feta, Ricotta, Phyllo Pastry, Farro, Wholewheat Couscous, Stale Bread, Dill, Spring
  Onion, Dijon Mustard, Red Wine Vinegar, Lemon Juice. (Fennel, radish and pecorino appeared
  only in the crudité platter and the hummus, both of which are skipped.)
- Units are `g` / `ml` / `piece` only; `kg` and `l` are formatting, not storage.

### Lemon

Existing `Lemon` (id 953) is stored as `piece` but holds values of 8–40 — millilitres of
juice recorded in the wrong dimension. The 29 new recipes do not inherit that error and do
not correct it either: they use a **new `Lemon Juice` ingredient in `ml`**, and reference
id 953 only where a whole fruit is meant (zest, wedges), as honest piece counts. Id 953's
existing rows are left exactly as they are.

### Known flaws left alone

Recorded here, not fixed, at the user's instruction — the account has no backups:

- `Garlic` (917, `g`) and `garlic cloves` (1109, `piece`) are duplicates.
- `Capers` (1108) is `ml` in one recipe and `g` in another.
- `Lemon` (953) as above.

The new recipes use `Garlic` 917 in grams and `Capers` 1108 in grams, so they at least do
not deepen the split.

### Tags

Reuse by name (import matches tags by name in merge mode): `vegetarian`, `vegan`, `quick`,
`cheap`, `low calories`, `mediterranean`. New: `make-ahead`, `no-cook`, `phyllo`,
`high-protein`, `legumes`, `summer`, `oven`.

### bulk_prep

True where the source says the dish keeps four days and improves — gazpacho, courgettes
in scapece, lentil salad, roasted peppers, confit tomatoes, the pepper-and-feta and
cannellini spreads, and the baked trays. This is what makes the
planner's leftover soft-hold reserve future slots for them.

## Verification

Test-first, against the real import path rather than a hand-read of the JSON:

1. A pytest that loads the generated file through `crud.import_data(..., mode="merge")`
   into a database seeded with a copy of the user's export, asserting:
   - 24 recipes are added and the existing 44 survive;
   - no imported title collides with an existing one — the duplicate skip is asserted,
     not merely intended;
   - no ingredient is created whose name already existed (the duplicate check);
   - every ingredient line has a unit, and every unit is one of `g`/`ml`/`piece`;
   - every recipe has `servings == 4`, a non-empty procedure, and at least three ingredients;
   - the courses split 5 / 7 / 12 across `first-course` / `main` / `side`;
   - `favorite_side_ids` is empty everywhere (nothing points at an id we do not own).
2. Each recipe's total weight is sanity-checked to fall in a plausible band for four
   portions, catching a scaling slip that a schema check would pass.
3. `/simplify` as the final step.

## Report

A companion Markdown file listing the five skipped recipes with what they duplicate, and
then, per imported recipe: the source number, the scaling applied, every
corrected quantity with its reason, and every inferred `season_months` / conversion value —
so the user can audit the inference rather than trust it.
