# Mobile UX: Recipes and Shopping List — Design Spec

Date: 2026-08-29
Branch: `mobile-ux-calendar`

---

## Context

Branch `mobile-ux-calendar` fixed the meal-plan calendar and raised `Button`/`Input`
to touch-safe sizes. The Recipes and Shopping List pages were never revisited, and
the user reports concrete breakage on a phone:

1. The Recipes header buttons wrap their labels and end up different heights.
2. Shopping List renders three full-width month calendars stacked vertically.
3. Portion/batch numbers land on their own line, misaligned.

An audit of [`RecipesPage.jsx`](../../../frontend-v2/src/pages/RecipesPage.jsx),
[`ShoppingListPage.jsx`](../../../frontend-v2/src/pages/ShoppingListPage.jsx) and their
components found the causes and several adjacent problems. This spec covers the fix.

### Root causes found

| Symptom | Cause |
|---|---|
| Header buttons wrap, unequal heights | `RecipesPage.jsx:245` inner cluster is `flex items-center gap-2` with **no** `flex-wrap`, holding four controls. `Input` is `w-full` below 640px and has no `min-w-0`, so it cannot shrink; the two text buttons starve and wrap their labels. `Button` uses `min-h-11`, not a fixed height, so a wrapped button is ~60px beside a 44px sibling. The unequal heights are a *symptom of the wrap*, not a separate bug. |
| Three stacked calendars | `ShoppingListPage.jsx:104` hardcodes `length: 3`; the container is `basis-full sm:basis-[30%]`, so all three go full-width below 640px. The calendar is read-only — it only tints a range the `DateRangePicker` directly above already states in words. |
| "Portions on a new line" (Recipes) | `RecipesPage.jsx:335` is `flex items-center gap-1` around `{course} · {n} ingredients · serves {basis}`. Flex makes each text run an unbreakable item, no `flex-wrap`, so "serves N" strands at a 150px card width. |
| "Portions on a new line" (Shopping) | `ShoppingListPage.jsx:283` is `flex items-baseline gap-2` holding the title and the `×2` batch label, no wrap. A long title pushes the label onto its own unaligned line. |

### Also found, in scope

- Filter popover: 16px native checkboxes (guide floor is 44px), three nested
  `max-h-40` scroll areas inside a 224px popover inside the page scroll, no
  outside-click or Esc dismissal, and **no indication that a filter is active**
  once closed.
- Detail modal: Delete is `size="sm"` (36px), adjacent to Edit, and fires
  immediately with no confirmation or undo.
- Shopping list: ingredient rows are `<li onClick>` — no button semantics, no
  keyboard access, no visible affordance for "tap to cross off".
- Mobile reading order puts up to 14 meals above the ingredient list.
- No empty states on either page.
- Shopping list header `flex items-end gap-2` does not wrap; overflows at 320px.

---

## Scope boundary

**Every layout change is below the `md` breakpoint**, gated by the existing
`useIsMobile` hook ([`hooks/useIsMobile.js`](../../../frontend-v2/src/hooks/useIsMobile.js)) —
the same mechanism `MealPlanCalendar` and `MobileCollapse` use, sanctioned by design
guide §8.3. Its own comment is the governing rule: use it *only where a phone needs
different markup*; anything expressible as a `md:` class stays a class.

Desktop keeps, untouched: the Recipes header layout, the filter popover's *surface*
(it stays a popover), the `DateRangePicker`, the three-month calendar, and the
`md:grid-cols-2` two-column shopping layout.

A small set of changes are **behaviour or accessibility rather than layout**, and are
wrong at every width — so they apply at **all** widths, not only below md:

- ingredient rows become real buttons instead of `<li onClick>` (§5);
- a ticked ingredient unticks when its quantity changes (§5);
- the funnel carries an active-filter count badge, and active filters show as
  removable chips with a *Clear all* (§2) — today a closed popover leaves a filtered
  grid with no explanation on desktop just as much as on a phone;
- the filter popover gains outside-click and Esc dismissal (§2);
- Delete asks for confirmation and the modal's action buttons reach 44px (§3).

Their desktop *appearance* changes only marginally: a checkbox mark appears where the
strike-through already was, a badge appears on the funnel, and a chip row appears
under the search box when filters are active. No desktop layout moves.

---

## §1 — Recipes: mobile header

Below md the header is:

```
Recipes
[ Search recipes…                    ] [⛛]
```

- `Input` becomes `flex-1 min-w-0` (the missing `min-w-0` is what makes the row
  unsqueezable today); the `sm:w-56` is replaced by an `md:`-scoped width.
- The funnel becomes a 44px `IconButton` carrying `FunnelIcon` — the icon already in
  use, from `@heroicons/react/24/outline`.
- Both text buttons leave the row.

A **floating action button** takes their place: 56px, circular, `PlusIcon`, `--c-a2`
accent, `position: fixed`, bottom-right, offset above `env(safe-area-inset-bottom)`.
Tapping it opens a bottom sheet with exactly two choices:

| Choice | Icon | Opens |
|---|---|---|
| Write it myself | `PencilSquareIcon` | existing `NewRecipeModal` |
| Import from a website | `GlobeAltIcon` | existing `ImportRecipeModal` |

The recipe grid gains bottom padding equal to the FAB's height plus its offset, so
the FAB never covers the last row.

This dissolves both reported header bugs structurally rather than by tuning classes:
there is one control left on the row, and it is a circle.

`data-tour` anchors (`recipes-import`, `recipes-new`) move onto the FAB so the
tutorial still has something to point at on a phone.

## §2 — Recipes: filter

Below md, `FunnelIcon` opens a **bottom sheet** instead of the popover.

- Built on the existing `ModalScrim` ([`components/Modal.jsx`](../../../frontend-v2/src/components/Modal.jsx)),
  which already owns the wash, the `Z.modal` stacking order and the overflow rules.
- Content: one section per group — Course, Tags, Ingredients — each a wrapped set of
  `ToggleChip`s raised to a 44px target. **One** scroll region, not three nested.
- Footer: a primary "Show N recipes" button that closes the sheet, where N is the
  live filtered count.
- Dismissal: backdrop tap, Esc, or the footer button.

Added at **both** breakpoints, because their absence is a correctness problem rather
than a mobile one:

- a count badge on the funnel showing the number of active filters;
- a row of removable active-filter chips beneath the search box, each with an ✕,
  plus a *Clear all*;
- outside-click and Esc dismissal for the desktop popover too — `DateRangePicker`
  already implements exactly this pattern and is the reference.

## §3 — Recipes: cards and detail modal

**Card meta line.** Becomes plain flowing text, not a flex row:

```
main · 8 ingr · 4p
```

Fits one line at the 150px mobile card width, so cards keep a uniform height and the
grid stops rippling. Full words are retained at md and above.

**Card title.** Gains `line-clamp-2`, the treatment `MealCard` already received, so
one long name stops reflowing its grid row.

**Detail modal actions.** Share and Edit stay as the primary pair, raised from
`size="sm"` (36px) to 44px. **Delete separates onto its own row** in quieter styling
and routes through a new `ConfirmModal`:

> Delete «title»? This can't be undone.

**Empty states.** Two: "no recipes yet" (offering the starter pack), and "nothing
matches these filters" (offering *Clear all*).

## §4 — Shopping list: layout

Below md:

- **One** `MonthGrid`, for the start date's month — matching the existing
  `months` calculation, which is already anchored on `startDate`. Days falling in a
  following month are simply not shown; the date pill states the full range in words.
- Header controls (`DateRangePicker` + People) allowed to wrap.
- The two `Card`s are replaced by a **two-state toggle**:

```
[ Ingredients ][ Meals ]
```

**Ingredients is the default tab** — it is what you hold up in a shop.

The toggle is the existing `CalendarViewToggle`, which is already precisely this
control (`aria-pressed` buttons, `min-h-11`, `--c-pos` active fill) and whose own
doc comment explains why it is deliberately not `SegmentedControl`. It is misnamed
for its actual generality, so this spec **renames it to `ViewToggle`** and updates
its `MealPlanCalendar` call site and the barrel export.

At md and above nothing changes: three months, both cards side by side.

## §5 — Shopping list: ticking off

`buildShoppingList` keys each row as `name.toLowerCase() + '||' + unit`
([`utils/shoppingList.js:52`](../../../frontend-v2/src/utils/shoppingList.js#L52)) — no
amount, no recipe, no date. That makes identity stable across plan changes and is
what allows the following to be simple.

**Storage stays in memory**, as today. Ticks are a scratch pad for one visit; there
is no localStorage key and no backend model, so no migration and no
`seed_testing_data.py` change.

**`crossed` changes from `Set<key>` to `Map<key, amountAtTick>`.** A row renders
ticked only while `crossed.get(key) === ing.amount`. Consequences:

- Changing a head-count so a quantity changes silently drops the tick — correct,
  since the amount you verified is no longer the amount you need.
- It requires no effect, no listener and no invalidation pass: it falls out of the
  render, and stale entries are inert.
- `handleLoad` keeps clearing it on a range change.

**Rows become `<button aria-pressed>`** at a 44px target with a visible checkbox mark
(`CheckIcon` when ticked), replacing `<li onClick>`. This states the affordance,
which today is invisible, and makes the list keyboard-reachable. Applies at all
widths.

**Batch label.** `flex items-baseline gap-2` becomes inline text flow, so `×2` sits
after a long title instead of stranding on its own line.

**Empty states.** "No meals planned in this range" and, consequently, an empty
ingredient list that says so.

## §6 — Shared code

**New components**

| Component | Built on | Used by |
|---|---|---|
| `BottomSheet` | `ModalScrim` | §1 create sheet, §2 filter sheet |
| `Fab` | `IconButton` | §1 |
| `ConfirmModal` | `Modal` | §3 |

**Renamed:** `CalendarViewToggle` → `ViewToggle` (call site + barrel + its test file).

**Reused unchanged:** `ModalScrim`, `Z`/`SCRIM` from `lib/layers.js`, `IconButton`,
`ToggleChip`, `Modal`, `Input`, `Button`, `Card`, `MonthGrid`, `useIsMobile`,
`buildShoppingList`, `batchLabel`, `basisOf`.

All new components are exported from `components/index.js`.

**Deliberately not reused:** `MobileCollapse` (the tabs replace stacking, they do not
collapse it) and `SegmentedControl` (a three-option icon-over-two-line-label control
that would have to be distorted into a two-state switch — `CalendarViewToggle`'s
comment already argues this).

---

## Implementation approach

Per `CLAUDE.md`, this is built under `/test-driven-development`: a failing
vitest + React Testing Library test before each behaviour, and the final step of the
plan is `/simplify`.

Tests are stated as behaviour, not markup. `useIsMobile` reads `window.matchMedia`
with an `innerWidth` fallback, so mobile branches are tested by stubbing
`matchMedia` — the pattern the existing `MealPlanCalendar` tests already use.

Behaviours to cover:

- **§1** FAB renders below md and not above it; it opens a sheet with two choices;
  each choice opens the correct existing modal; the header row holds only search and
  filter on mobile.
- **§2** Filter opens a sheet below md and the popover above it; chips toggle the
  filter; the funnel badge counts active filters; active-filter chips remove
  individually; Clear all empties them; Esc and backdrop dismiss.
- **§3** Meta line text at mobile and desktop; title clamps; Delete asks before
  deleting; cancelling deletes nothing; confirming calls `recipesApi.delete`.
- **§4** One `MonthGrid` below md, three above; tab switch shows one list at a time
  below md and both above; Ingredients is the initial tab.
- **§5** Tapping a row ticks it; tapping again unticks; a quantity change unticks a
  ticked row and leaves others alone; export still excludes ticked rows; rows are
  reachable and toggleable by keyboard.

### Verification

Automated, from `frontend-v2/`:

```
npm run test     # vitest, single run
npm run lint     # eslint
npm run build
```

Manual, at 320 / 375 / 768 / 1280px, with **no horizontal page scroll at any width**:

1. Recipes: header holds two controls; FAB reaches both creation paths; filter sheet
   opens, filters, and dismisses three ways; the funnel badge and active chips agree
   with the grid; card meta is one line; Delete asks first.
2. Shopping list: one month below md and three above; tabs switch; Ingredients is
   first; ticking works by touch and by keyboard; changing a head-count unticks the
   affected row only; a long recipe title keeps its `×2` inline.
3. Desktop regression: header, `DateRangePicker`, three-month calendar and the
   two-column layout are visually identical to `main`.
4. Keyboard only: reach the FAB, the sheet, every chip and both modals by
   accessible name.

Still outstanding from the previous branch and worth folding into the same manual
pass: **focus an `Input` on a real iOS device and confirm the page does not zoom.**
That fix shipped in `c4be323` and has never been seen working on hardware.

---

## Out of scope

Previously agreed deferrals, none made worse here: the `sm:` → `md:` cleanup (this
spec removes four of the nine offenders as a side effect, but does not chase the
rest), `NavDrawer` focus trap and body-scroll lock, unused `--container-max`,
`index.html` title and `theme-color`, and the design-guide §1 radii contradiction.

No backend change. No schema change, therefore no Alembic revision and no
`seed_testing_data.py` update.

## Open risks

- The FAB overlaps the bottom of any page it is on; the grid padding must be
  verified against a filtered grid of exactly one row.
- Renaming `CalendarViewToggle` touches the meal-plan branch's work. It is a pure
  rename with one call site, but it must land as its own commit to stay reviewable.
