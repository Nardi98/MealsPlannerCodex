# Measurement Units: Storage, Conversion, and Import

**Date:** 2026-08-31
**Status:** Approved design, pending implementation plan

## Problem

Three failures compound in the current unit handling.

**Storage has units but no dimensions.** `UnitEnum` (`models.py`) is a flat list of
`g, kg, l, ml, piece` with nothing recording that `g`/`kg` are mass, `ml`/`l` are volume,
and `piece` is a count. Nothing can convert between them, and nothing tries.

**The shopping list splits on the unit string.** `buildShoppingList`
(`frontend-v2/src/utils/shoppingList.js`) keys entries on
`name.toLowerCase() + '||' + unit`, so an onion stored as `2 piece` by one recipe and
`200 g` by another produces two unrelated lines. The list the user shops from is wrong
whenever two recipes disagree, which is often.

**Import pushes the conversion outside the app.** `IMPORT_PROMPT`
(`frontend-v2/src/constants/recipeImport.js`) requires the chatbot to emit one of the five
stored units. A source saying "1 cup flour" or "2 onions" therefore forces the chatbot to
guess a conversion silently, with no record that a guess occurred and no way for the app to
check it. US recipes, which give nearly everything by volume, are the worst case.

`Ingredient.unit` and `RecipeIngredient.unit` may also disagree with no reconciliation.

## Core insight: two tiers of conversion

**Tier 1 — within a dimension.** Fixed, universal, ingredient-independent:
`1 cup = 236.6 ml`, `1 tbsp = 14.8 ml`, `1 oz = 28.35 g`, `1 lb = 453.6 g`. This is
arithmetic. It belongs in a hardcoded table in the app, is exactly testable, and involves no
LLM and no per-ingredient knowledge.

**Tier 2 — across dimensions.** Ingredient-specific physics, and the only genuinely hard
part: `ml -> g` needs a density, `piece -> g` needs a piece weight. Two numbers per
ingredient cover every case.

"1 cup of flour" is two hops: `1 cup -> 236.6 ml` (Tier 1, free) `-> 125 g` (Tier 2, needs
flour's density). The US-volume problem and the count-vs-weight problem are the same problem
and share one mechanism.

## Design

### Storage: base metric units only

`UnitEnum` becomes exactly `g`, `ml`, `piece` — one base unit per dimension. `kg` and `l`
are removed from storage and become *formatting*, on the same footing as `cup`: display
`1200 g` as `1.2 kg`. Imperial units never enter the database. A narrow storage vocabulary
is what makes aggregation well defined; the wide vocabulary lives only at the edges.

### `Ingredient`

- **Drop `unit`.** The ingredient no longer owns a canonical unit. Nothing is normalised at
  write time; recipes keep the dimension they were authored in, and unification happens at
  read time as a pure function of the conversions. This removes a whole class of data
  corruption: a bad conversion can produce a bad *display*, never bad stored data.
- **Add `grams_per_ml: float | null`** — density.
- **Add `grams_per_piece: float | null`** — weight of one unit.
- **Add `preferred_dimension: enum(mass, volume, piece) | null`** — a *display* preference
  deciding which value leads. Null falls back to the dimension most of the contributing
  recipes used, ties broken toward mass.

**Null conversions are meaningful, not missing.** Null means that dimension does not apply
to this ingredient — pieces of milk is a category error, not absent data. The converter
refuses to cross a null and the UI degrades honestly. **Nothing in this system ever invents
a conversion factor**, including no water-density default for unknown liquids.

`preferred_dimension` stores a *dimension*, not a unit, deliberately: `g` vs `kg` vs `oz` is
Tier 1 formatting already decided by the metric/US setting, so a unit-valued column would
encode the same choice twice and permit contradiction. The only question open per ingredient
is: weigh it, measure it, or count it.

### `RecipeIngredient`

`unit` remains authoritative and is always one of `g / ml / piece`. Both entry paths convert
into it at the door via the shared Tier 1 table.

### `utils/units.js` — one shared module

A single frontend module owning:

- the Tier 1 conversion table, both directions;
- `toBaseUnit(amount, unit)` -> `{ amount, unit }` in `g`/`ml`/`piece`;
- `convert(amount, fromDimension, toDimension, ingredient)`, returning null when the
  required factor is null;
- `formatAmount(amount, unit, system)`, applying metric/US rendering and `kg`/`l` promotion
  above 1000;
- piece rounding (below).

Manual entry, import, the recipe page, the shopping list, and the text export all call this
module. Having exactly one implementation is what prevents the two entry paths from
drifting apart.

### Manual recipe entry

The recipe form's unit field becomes a curated dropdown covering what people actually write:
`g, kg, oz, lb, ml, l, tsp, tbsp, cup, fl oz, piece, clove, slice`. On save it converts to
`g / ml / piece` through the Tier 1 table. The dropdown orders itself by the user's
metric/US setting so their usual units lead, without hiding the rest.

### Import

The prompt stops asking the chatbot to convert or to match the user's pantry, and asks only
for physical facts, which are identical for every user:

```json
{ "name": "onion", "quantity": 2, "unit": "piece", "grams_per_piece": 150 }
{ "name": "flour", "quantity": 1, "unit": "cup",   "grams_per_ml": 0.53 }
```

The prompt's accepted `unit` vocabulary widens to the manual-entry list plus count-ish words
(`clove`, `slice`, `bunch`) which normalise to `piece`; the chatbot's `grams_per_piece` is
then per clove, which is correct. Conversions are requested only where they make sense, and
omitting one is a valid answer meaning "this dimension does not apply".

On paste, per ingredient, with **no user interaction**:

1. Normalise the source unit to `g`/`ml`/`piece` via Tier 1.
2. Fuzzy-match the name against the user's ingredients, reusing the existing
   `IMPORT_SUGGESTION_THRESHOLD` machinery.
3. **Match found** — store the amount as normalised. Backfill any conversion the ingredient
   lacks. **On collision the database wins**: an existing factor is never overwritten by an
   import. The user may edit factors freely; no provenance flag is stored.
4. **No match** — create the ingredient with whatever conversions the reply supplied.

The same chatbot reply therefore yields correct data for every user regardless of how they
keep their pantry, because the app — the only party that knows the pantry — does all the
matching.

### Shopping list

Group by ingredient, then unify per dimension.

- **Conversions available** — one row. The primary value follows `preferred_dimension`, or
  the most-used-by-recipes fallback. Every other reachable form renders as a muted
  secondary.
- **Conversions missing** — one row per dimension (`Onions — 2` and `Onions — 150 g`),
  each flagged. The flag links directly to editing that ingredient's conversions, so the
  moment the gap is noticed is the moment it can be closed. This is the only friction in the
  design and it is opt-in. Rows self-heal once a factor exists.

The merge key drops the unit and becomes the ingredient identity.

### Recipe page

Same primary-plus-muted-secondary treatment, showing whichever alternate forms the
ingredient's conversions permit.

### Display: primary and secondary

One component, no breakpoint fork in the logic. Primary value in normal weight, secondary
smaller and muted using the existing `--text-subtle` token from
`MEAL_PLANNER_DESIGN_GUIDE.md` (no new colour). On desktop both sit inline; on mobile the
secondary drops below the primary or collapses behind a tap on the row. That is a CSS
decision only — the same data and the same component serve both.

### Rounding

Pieces round to the nearest quarter and never to zero (floor at a quarter: a recipe needing
*some* onion means buying one). Reuse the existing `FRACTIONS` map in `shoppingList.js`
rather than introducing a second notion of fractions. Mass and volume keep the current
2-decimal rounding, with `kg`/`l` promotion above 1000.

### User setting: `unit_system`

`metric` or `us`, **display-only**. The database is always metric; the setting is applied by
the frontend at render time, so toggling is instant, needs no round-trip, and cannot touch
stored data.

Switching between systems raises one popup: *"also switch your ingredients from weight to
volume?"* (or the reverse). Accepting flips `preferred_dimension` from `mass` to `volume` on
every ingredient holding a `grams_per_ml` that makes the switch meaningful. `piece` is never
touched. Ingredients lacking the needed factor stay as they are and are named in the result.
The popup does not appear when nothing is switchable.

This bulk operation is safe because it writes a *display preference*, never a quantity. A
wrong answer costs one click to reverse and cannot corrupt anything.

## Migration

Per `CLAUDE.md`, an Alembic revision ships in the same commit as the model change, and
`scripts/seed_testing_data.py` is updated in the same change so seeded data stays coherent.

1. Add `grams_per_ml`, `grams_per_piece`, `preferred_dimension` to `ingredients`.
2. Convert existing `kg` -> `g` and `l` -> `ml` rows (x1000) in `recipe_ingredients`.
3. Drop `ingredients.unit` (no data conversion needed — the column is discarded, and its
   values carry no information `recipe_ingredients` does not already hold).
4. Shrink `unit_enum` to `g, ml, piece`.
5. Add `unit_system` to user settings.

Steps 2-4 are hand-written: autogenerate does not compare enum values and cannot infer the
data conversion. `tests/test_migrations.py` catches drift against the models.

## Testing

Built test-first per `CLAUDE.md`.

**`utils/units.js`** — Tier 1 table in both directions and round-tripping; `toBaseUnit` over
the full dropdown vocabulary; `convert` across every dimension pair *including* every
null-factor branch, asserting it returns null rather than a number; `formatAmount` under
both systems, at the `kg`/`l` promotion boundary; piece rounding, especially the
never-round-to-zero floor.

**Shopping list** — mixed-unit occurrences merging to one row; the split-row path when a
factor is null, including the flag; primary-dimension selection from `preferred_dimension`
and from the most-used fallback with its tie-break; existing scaling by `people / servings`
preserved.

**Import** — parser accepts the widened vocabulary and normalises count-ish words; the
database-wins collision rule; backfill of absent factors; new-ingredient creation carrying
conversions; a reply omitting a conversion is accepted, not an error.

**Backend** — the migration; the enum rejects `kg`/`l`; the seed script produces coherent
data.

**Settings** — the bulk `preferred_dimension` switch flips only ingredients with the needed
factor, never touches `piece`, and reports what it skipped.

## Out of scope

- A curated built-in reference table of densities and piece weights. The import backfill
  gives the same coverage without the curation burden, and degrades to a user edit.
- Provenance flags distinguishing user-entered from chatbot-supplied factors. Decided
  against: low stakes, and the user can always edit.
- A persisted per-ingredient display toggle in the shopping list. Both values are already
  visible; there is nothing left to toggle.
- Any conversion invented by the app where a factor is null.
