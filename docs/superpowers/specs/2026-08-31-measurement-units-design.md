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

## Functional behaviour, surface by surface

### The mentality shift, stated

Today a quantity is *a number plus a string*, and the string is opaque: two strings either
match or they don't. After this change a quantity is *a physical amount that happens to be
written in one of several equivalent ways*, and the unit is a **view** of it rather than a
property of it.

Three consequences follow, and every behaviour below is one of them applied to a screen:

1. **The user's chosen unit is an input and a display choice, never a constraint on
   storage.** Whatever they type is accepted and normalised; whatever they prefer to read is
   rendered from the same stored number.
2. **The app knows what it does not know.** A null conversion is a recorded fact — "this
   ingredient has no meaningful volume" — distinct from "nobody has told us yet". Where a
   value genuinely cannot be derived, the app says so instead of guessing.
3. **Knowledge accumulates without being asked for.** Every import teaches the pantry
   something, permanently, for free. The system gets more capable the more it is used, and
   the user never fills in a form to make that happen.

### Ingredient editor (`AddIngredientModal`, `EditIngredientModal`)

The `unit` field is removed. In its place, an optional **"How this ingredient converts"**
group, written in plain language rather than schema names:

- *"One piece weighs ___ g"* -> `grams_per_piece`
- *"100 ml weighs ___ g"* -> `grams_per_ml`, entered per 100 ml because that is the scale
  people can estimate, and divided by 100 on save

Both empty by default, both optional. Helper text states the rule explicitly: **leave a
field blank when that measurement makes no sense for this ingredient** — milk has no piece
weight, eggs have no useful density. Blank is a legitimate, permanent answer, not an
outstanding task, and the UI must never nag about it.

A third control, **"Usually measured by"** (`preferred_dimension`), offers only the
dimensions the conversions actually make reachable, plus an "Automatic" default meaning
null. Filling in a piece weight is therefore what *unlocks* the option to count that
ingredient — cause and effect the user can see happening.

### Ingredients page (`IngredientsPage`, `IngredientCard`)

Each card shows which measurements the ingredient can be expressed in, as small badges
(`g` / `ml` / `piece`), derived from its conversions. This makes the pantry's knowledge
visible at a glance and gives the shopping list's "fix this" links somewhere coherent to
land.

No warning state, no completeness meter, no "3 ingredients need attention" banner. A
single-dimension ingredient is a normal ingredient, not a broken one.

### Merging ingredients (`MergeIngredientsModal`, `crud.merge_ingredients`)

The merge API's `surviving_unit` and `conversion_factor` fields are removed. They exist only
because units were opaque strings needing a hand-supplied bridge; the ingredient's own
conversions now supply it. Merge becomes:

- Recipe lines re-point to the target and are converted into the target's dimensions where
  the target's conversions allow; where they don't, lines keep their own dimension and the
  merged ingredient simply spans two, which the shopping list already renders correctly.
- Conversions union onto the target, **target wins on collision**, matching the import rule.
  A merge can therefore only ever *add* knowledge.
- `preferred_dimension` follows the target.

### Recipe create / edit (`NewRecipeModal`)

The amount field gains the curated unit dropdown described above. Two behaviours make the
normalisation honest rather than surprising:

- **Echo on entry.** Typing `1 cup` shows `= 237 ml` beside the field as it is typed. The
  user sees the conversion happen and can correct the unit before saving. Nothing is
  silently rewritten under them.
- **Round-trip on reopen.** Reopening the recipe shows `237 ml`, not `1 cup`, because the
  source unit is deliberately not stored. The echo is what makes this acceptable: the user
  already watched the conversion and agreed to it.

An ingredient the recipe measures in a dimension the ingredient has no conversion for is
still allowed, and is exactly how a second dimension legitimately enters the system.

### Recipe view and shared recipes (`RecipesPage`, `SharedRecipePage`, public pages)

Ingredient lines use the primary-plus-muted-secondary display, showing every alternate form
the conversions permit. The existing servings scaling composes with it: scale first in the
stored unit, then render, so rounding is applied once, at the end, and never compounds.

The public share renderer's current `link.unit or link.ingredient.unit` fallback
(`public_schema.py`, `recipe_copy.py`) disappears with `Ingredient.unit`; the line's own unit
is now always authoritative. **Copying a shared recipe** into your own collection follows
the import rule: conversions are backfilled onto matched ingredients, never overwritten.

### Import (`ImportRecipeModal`)

The flow the user sees is unchanged — paste, review, save — and gains **no new questions**.
What changes is a quiet receipt in the review step:

> *Learned: onion ≈ 150 g each · flour ≈ 53 g per 100 ml*

Only genuinely new facts appear; anything the database already knew is silently kept and not
mentioned. The receipt is informational, dismissible, and blocks nothing. Its purpose is to
make the accumulation in principle 3 visible, so the user understands why imports keep
getting better, and to give them a chance to catch an obviously wrong number without ever
being required to look.

Conversions the reply omits are recorded as null and never invented (principle 2).

### Starter recipes (`StarterRecipesModal`) and seeded data

The shipped starter recipes and `seed_testing_data.py` carry conversions on every ingredient
where they make sense, and deliberately omit them on a few where they do not. A new user's
pantry therefore arrives already able to unify, and the seed exercises the null path rather
than pretending it is rare.

### Shopping list (`ShoppingListPage`)

- **Unified row** — one line per ingredient, primary value plus muted alternates.
- **Split row** — when a conversion is missing, one line per dimension, each carrying a
  quiet marker. Tapping the marker opens that ingredient's editor focused on the missing
  field. The single friction point in the design is placed at the exact moment the user has
  a reason to care, and it is skippable.
- **Checking off** operates on the ingredient, so a split ingredient's rows check off
  together. The user is buying one thing.
- **Text export** (`formatExportText`) renders the primary value only. A pasted list should
  read like a list, not a conversion table.

### Settings

A `unit_system` control, `metric` or `us`, taking effect immediately with no save step,
because it touches no data. Switching raises the one popup: *"US recipes usually measure by
volume. Switch your ingredients from weight to volume where possible?"* with Switch / Keep
as they are.

Accepting flips `preferred_dimension` on every ingredient whose conversions support it,
leaves `piece` untouched, and reports plainly what it skipped and why. Declining changes
nothing but the rendering units. The popup does not appear when nothing is switchable.

### Data import / export (`ImportExportPage`)

The JSON payload carries the new ingredient fields. Imports from a payload predating this
change are valid: absent conversions read as null, and the data behaves exactly as it does
today.

### Invariants the app must never violate

- Never invent a conversion factor, including no water-density default.
- Never overwrite a stored conversion with an imported one.
- Never block a save, an import, or a shopping list on a missing conversion.
- Never ask the user for a conversion; only ever offer.
- Never rewrite a stored quantity as a side effect of a *display* setting.
- Never present a single-dimension ingredient as incomplete or in error.

### Behaviour before any conversions exist

Every ingredient in an existing account starts with both conversions null. The app then
behaves as it does today — mixed-dimension ingredients split into rows — except that the
split is now visible, explained, and one tap from being fixed. Nothing regresses on day one,
and the system improves from the first import onward without a migration of user knowledge
or a setup wizard.

## Migration

Per `CLAUDE.md`, an Alembic revision ships in the same commit as the model change, and
`scripts/seed_testing_data.py` is updated in the same change so seeded data stays coherent.

1. Add `grams_per_ml`, `grams_per_piece`, `preferred_dimension` to `ingredients`.
2. Convert existing `kg` -> `g` and `l` -> `ml` rows (x1000) in `recipe_ingredients`.
3. Drop `ingredients.unit` (no data conversion needed — the column is discarded, and its
   values carry no information `recipe_ingredients` does not already hold).
4. Shrink `unit_enum` to `g, ml, piece`.
5. Add `unit_system` to user settings.

Alongside the schema work, the API surface changes: `IngredientCreate`, `IngredientUpdate`,
`IngredientSummary`, `IngredientIn`/`IngredientOut` drop `unit` and gain the two conversions
and `preferred_dimension`; `IngredientMergeRequest` drops `surviving_unit` and
`conversion_factor`; and the `link.unit or link.ingredient.unit` fallbacks in
`public_schema.py` and `recipe_copy.py` are removed.

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
data including deliberate null-conversion ingredients; `merge_ingredients` converting via
the target's conversions, unioning with target-wins, and leaving unconvertible lines in
their own dimension; copying a shared recipe backfilling without overwriting; the public
share payload after the `ingredient.unit` fallback is removed; JSON import of a
pre-change payload reading conversions as null.

**Recipe form** — the entry echo showing the converted value as the user types; save storing
the base unit; reopening rendering the stored unit.

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
