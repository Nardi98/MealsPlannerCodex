# Mobile UX: Recipes and Shopping List — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Recipes and Shopping List pages usable on a phone, fixing the wrapping header buttons, the three stacked month calendars, and the stranded portion numbers, without changing any desktop layout.

**Architecture:** All layout branching goes through the existing `useIsMobile` hook (JS branch, not `md:` classes) because these are *different markup*, not different CSS. Three new presentational components — `BottomSheet`, `Fab`, `ConfirmModal` — are built on the existing `ModalScrim`/`Modal` primitives so the scrim, the `Z` stacking order and the overflow rules stay in one place. The shopping list's crossed-off state changes from `Set<key>` to `Map<key, amountAtTick>`, which makes "untick when the quantity changes" fall out of the render with no effect and no invalidation pass.

**Tech Stack:** React 19, Vite, Tailwind 3, `@heroicons/react/24/outline`, vitest + React Testing Library + jsdom.

**Spec:** `docs/superpowers/specs/2026-08-29-mobile-recipes-shopping-design.md`

**Working directory for every command: `frontend-v2/`.**

---

## Conventions for every task

Test files start with the jsdom docblock and the jest-dom import, matching every existing test in this repo:

```jsx
/**
 * @vitest-environment jsdom
 */
import React from 'react'
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import '@testing-library/jest-dom/vitest'
```

Mobile branches are tested with the existing helper `src/test/stubViewport.js`:

```jsx
import { stubViewport } from '../../test/stubViewport'
stubViewport(true)   // below md
stubViewport(false)  // md and above
```

**Important:** when `matchMedia` is *not* stubbed, `useIsMobile` falls back to `window.innerWidth < 768`, and jsdom's default width is 1024. So every existing test without a `stubViewport` call runs as **desktop**. That is why the existing Recipes and Shopping List tests keep passing through most of this plan.

---

## File Structure

**New files**

| File | Responsibility |
|---|---|
| `src/components/BottomSheet.jsx` | A sheet anchored to the bottom of the viewport, on `ModalScrim`. Backdrop + Esc dismissal, optional sticky footer. |
| `src/components/Fab.jsx` | The 56px circular floating action button, safe-area aware. |
| `src/components/ConfirmModal.jsx` | A yes/no confirmation over another dialog, on `Modal` at `Z.nested`. |
| `src/components/RecipeFilters.jsx` | The three filter groups as chips, shared by the mobile sheet and the desktop popover so the two can never drift. |
| `src/components/ActiveFilterChips.jsx` | The removable active-filter row plus *Clear all*. |
| `src/components/__tests__/BottomSheet.test.jsx` | |
| `src/components/__tests__/ConfirmModal.test.jsx` | |
| `src/components/__tests__/Fab.test.jsx` | |

**Renamed**

| From | To |
|---|---|
| `src/components/CalendarViewToggle.jsx` | `src/components/ViewToggle.jsx` |

**Modified**

- `src/pages/RecipesPage.jsx` — header, filter surface, card meta, detail actions, empty states
- `src/pages/ShoppingListPage.jsx` — month count, tabs, batch label, crossed map, row semantics, empty states
- `src/components/MealPlanCalendar.jsx` — the `ViewToggle` rename only
- `src/components/index.js` — barrel exports
- `src/tutorial/steps.js` — tour anchors that move onto the FAB
- `src/pages/__tests__/RecipesPage.test.jsx` — the delete test gains a confirmation step

---

## Task 1: Rename `CalendarViewToggle` to `ViewToggle`

The component is a generic two-state `aria-pressed` switch; only its name is calendar-specific, and Task 10 needs it for the shopping list. A pure rename, landed alone so it stays reviewable.

**Files:**
- Rename: `src/components/CalendarViewToggle.jsx` → `src/components/ViewToggle.jsx`
- Modify: `src/components/index.js`, `src/components/MealPlanCalendar.jsx`

- [ ] **Step 1: Rename the file with git so history follows**

```bash
git mv src/components/CalendarViewToggle.jsx src/components/ViewToggle.jsx
```

- [ ] **Step 2: Rename the function and update its doc comment**

In `src/components/ViewToggle.jsx`, replace the doc comment and signature:

```jsx
/**
 * A two-state switch: a pair of labelled buttons in a bordered track, the
 * active one filled.
 *
 * Plain buttons with `aria-pressed` rather than a tablist: `SegmentedControl`
 * is the project's tablist primitive and implements roving focus and arrow
 * keys, and a `role="tablist"` that ignores arrow keys is a worse promise than
 * no tablist at all. This is a two-state switch, not a tab strip.
 *
 * `options` is a list of `[value, label]` pairs.
 */
export default function ViewToggle({ value, onChange, options }) {
```

The body is unchanged.

- [ ] **Step 3: Update the barrel export**

In `src/components/index.js`, replace the `CalendarViewToggle` line with:

```js
export { default as ViewToggle } from './ViewToggle'
```

Keep it in the alphabetical neighbourhood of the other `V`/`U` exports rather than leaving it among the `Calendar*` group.

- [ ] **Step 4: Update the one call site**

```bash
grep -rn "CalendarViewToggle" src/
```

Replace every hit in `src/components/MealPlanCalendar.jsx` (the import and the JSX tag) with `ViewToggle`. If a test file references it, update that too.

- [ ] **Step 5: Verify nothing references the old name**

Run: `grep -rn "CalendarViewToggle" src/`
Expected: no output.

- [ ] **Step 6: Run the full suite**

Run: `npm run test`
Expected: PASS, same count as before (569).

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "Rename CalendarViewToggle to ViewToggle

The component is a generic two-state aria-pressed switch; only its name
was calendar-specific, and the shopping list now needs the same control.
Pure rename, no behaviour change."
```

---

## Task 2: Recipe card meta line and title clamp

The meta line is a `flex` row, so `serves 4` cannot wrap mid-run and strands at a 150px card. It becomes plain flowing text, abbreviated on mobile.

**Files:**
- Modify: `src/pages/RecipesPage.jsx` (the card body, around line 335)
- Test: `src/pages/__tests__/RecipesPage.test.jsx`

- [ ] **Step 1: Write the failing tests**

Append to `src/pages/__tests__/RecipesPage.test.jsx`. Note the file does not currently import `stubViewport`; add it to the imports at the top:

```jsx
import { stubViewport } from '../../test/stubViewport'
```

```jsx
test('the card meta line is abbreviated on mobile so it fits one line', async () => {
  stubViewport(true)
  recipesApi.fetchAll.mockResolvedValue([
    {
      id: 1,
      title: 'Ribollita',
      course: 'main',
      servings: 4,
      tags: [],
      ingredients: [{ name: 'Cavolo nero' }, { name: 'Fagioli' }],
    },
  ])
  tagsApi.fetchAll.mockResolvedValue([])
  ingredientsApi.fetchAll.mockResolvedValue([])

  render(<RecipesPage />)

  expect(await screen.findByText('main · 2 ingr · 4p')).toBeInTheDocument()
})

test('the card meta line keeps full words on desktop', async () => {
  stubViewport(false)
  recipesApi.fetchAll.mockResolvedValue([
    {
      id: 1,
      title: 'Ribollita',
      course: 'main',
      servings: 4,
      tags: [],
      ingredients: [{ name: 'Cavolo nero' }, { name: 'Fagioli' }],
    },
  ])
  tagsApi.fetchAll.mockResolvedValue([])
  ingredientsApi.fetchAll.mockResolvedValue([])

  render(<RecipesPage />)

  expect(
    await screen.findByText('main · 2 ingredients · serves 4'),
  ).toBeInTheDocument()
})
```

- [ ] **Step 2: Run to verify they fail**

Run: `npm run test -- RecipesPage`
Expected: FAIL — both new tests, "Unable to find an element with the text". The existing `serves 4` test (`/serves 4/i`) still passes, because it is a regex against the desktop string.

- [ ] **Step 3: Implement**

In `src/pages/RecipesPage.jsx`, add the hook import near the other imports:

```jsx
import { useIsMobile } from '../hooks/useIsMobile'
```

Inside `RecipesPage`, near the other hooks:

```jsx
const isMobile = useIsMobile()
```

Replace the meta `div` in the card body with a single text node. A `flex` container makes each text run an unbreakable item; a plain block lets the browser break the line where it likes:

```jsx
<div
  style={{
    fontSize: 'var(--text-xs)',
    color: 'var(--text-subtle)',
  }}
>
  {isMobile
    ? `${r.course} · ${(r.ingredients || []).length} ingr · ${basisOf(r.servings)}p`
    : `${r.course} · ${(r.ingredients || []).length} ingredients · serves ${basisOf(r.servings)}`}
</div>
```

And add the clamp to the title `div` directly above it — it currently has no `className`:

```jsx
<div
  className="line-clamp-2"
  style={{
    fontFamily: 'var(--font-display)',
    fontWeight: 'var(--weight-semibold)',
    fontSize: 'var(--text-sm)',
    color: 'var(--text-strong)',
    lineHeight: 1.3,
  }}
>
  {r.title}
</div>
```

- [ ] **Step 4: Run to verify they pass**

Run: `npm run test -- RecipesPage`
Expected: PASS, all tests in the file.

- [ ] **Step 5: Commit**

```bash
git add src/pages/RecipesPage.jsx src/pages/__tests__/RecipesPage.test.jsx
git commit -m "Stop the recipe card meta line stranding its portion count

The line was a flex row, so each text run was an unbreakable item and
'serves 4' had nowhere to go at a 150px card width. It is now plain
flowing text, abbreviated below md where the space actually runs out.
The title gains the line-clamp MealCard already has, so one long name
stops reflowing its grid row."
```

---

## Task 3: `ConfirmModal` and the guarded delete

Delete is a 36px button beside Edit that fires immediately with no undo — the one destructive action in the app.

**Files:**
- Create: `src/components/ConfirmModal.jsx`, `src/components/__tests__/ConfirmModal.test.jsx`
- Modify: `src/components/index.js`, `src/pages/RecipesPage.jsx`, `src/pages/__tests__/RecipesPage.test.jsx`

- [ ] **Step 1: Write the failing component test**

Create `src/components/__tests__/ConfirmModal.test.jsx`:

```jsx
/**
 * @vitest-environment jsdom
 */
import React from 'react'
import { render, screen, fireEvent, cleanup } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import '@testing-library/jest-dom/vitest'
import ConfirmModal from '../ConfirmModal'

afterEach(() => cleanup())

test('confirming calls onConfirm', () => {
  const onConfirm = vi.fn()
  render(
    <ConfirmModal
      title="Delete Risotto?"
      message="This can't be undone."
      confirmLabel="Delete"
      onConfirm={onConfirm}
      onCancel={() => {}}
    />,
  )

  fireEvent.click(screen.getByRole('button', { name: 'Delete' }))

  expect(onConfirm).toHaveBeenCalledTimes(1)
})

test('cancelling calls onCancel and never onConfirm', () => {
  const onConfirm = vi.fn()
  const onCancel = vi.fn()
  render(
    <ConfirmModal
      title="Delete Risotto?"
      message="This can't be undone."
      confirmLabel="Delete"
      onConfirm={onConfirm}
      onCancel={onCancel}
    />,
  )

  fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))

  expect(onCancel).toHaveBeenCalledTimes(1)
  expect(onConfirm).not.toHaveBeenCalled()
})

test('Escape cancels', () => {
  const onCancel = vi.fn()
  render(
    <ConfirmModal
      title="Delete Risotto?"
      message="This can't be undone."
      confirmLabel="Delete"
      onConfirm={() => {}}
      onCancel={onCancel}
    />,
  )

  fireEvent.keyDown(document, { key: 'Escape' })

  expect(onCancel).toHaveBeenCalledTimes(1)
})
```

- [ ] **Step 2: Run to verify it fails**

Run: `npm run test -- ConfirmModal`
Expected: FAIL — "Failed to resolve import ../ConfirmModal".

- [ ] **Step 3: Implement**

Create `src/components/ConfirmModal.jsx`:

```jsx
import React from 'react'
import { ModalScrim } from './Modal'
import { Card } from './Card'
import { Button } from './Button'
import { Z } from '../lib/layers'

/**
 * A yes/no gate in front of an action that cannot be undone.
 *
 * Rendered at `Z.nested` because it is always raised from inside another
 * dialog — the recipe detail modal — and would otherwise sit beneath it.
 * Cancel is the safe default and comes first in the tab order; the confirm
 * button carries the caller's verb ("Delete") rather than a bare "OK", so the
 * button says what it will do without the message having to be read.
 */
export default function ConfirmModal({
  title,
  message,
  confirmLabel,
  onConfirm,
  onCancel,
}) {
  React.useEffect(() => {
    const onKey = (e) => {
      if (e.key === 'Escape') onCancel()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onCancel])

  return (
    <ModalScrim z={Z.nested} onClick={onCancel}>
      <Card
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onClick={(e) => e.stopPropagation()}
        style={{ width: '100%', maxWidth: 380, padding: 24, boxSizing: 'border-box' }}
      >
        <h3
          style={{
            margin: '0 0 8px',
            fontSize: 'var(--text-lg)',
            fontWeight: 'var(--weight-semibold)',
            color: 'var(--text-strong)',
          }}
        >
          {title}
        </h3>
        <p style={{ margin: '0 0 20px', fontSize: 'var(--text-sm)', color: 'var(--text-muted)' }}>
          {message}
        </p>
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onCancel}>
            Cancel
          </Button>
          <Button variant="danger" onClick={onConfirm}>
            {confirmLabel}
          </Button>
        </div>
      </Card>
    </ModalScrim>
  )
}
```

- [ ] **Step 4: Export it**

Add to `src/components/index.js`:

```js
export { default as ConfirmModal } from './ConfirmModal'
```

- [ ] **Step 5: Run to verify it passes**

Run: `npm run test -- ConfirmModal`
Expected: PASS, 3 tests.

- [ ] **Step 6: Update the existing delete test, which this is about to break**

In `src/pages/__tests__/RecipesPage.test.jsx`, the test `deletes a recipe from the detail modal` clicks Delete and expects the API call. Replace its two action lines and add a second test. Find:

```jsx
  fireEvent.click(await screen.findByText('Risotto'))
  fireEvent.click(await screen.findByText('Delete'))

  await waitFor(() => expect(screen.queryByText('Risotto')).toBeNull())
  expect(recipesApi.delete).toHaveBeenCalledWith(1)
```

Replace with:

```jsx
  fireEvent.click(await screen.findByText('Risotto'))
  fireEvent.click(await screen.findByRole('button', { name: 'Delete' }))
  // The delete is now guarded: the first click only asks.
  fireEvent.click(
    await screen.findByRole('button', { name: 'Delete recipe' }),
  )

  await waitFor(() => expect(screen.queryByText('Risotto')).toBeNull())
  expect(recipesApi.delete).toHaveBeenCalledWith(1)
```

And append a new test:

```jsx
test('cancelling the delete confirmation keeps the recipe', async () => {
  recipesApi.fetchAll.mockResolvedValue([
    { id: 1, title: 'Risotto', course: 'main', tags: [], ingredients: [], procedure: '' },
  ])
  tagsApi.fetchAll.mockResolvedValue([])
  ingredientsApi.fetchAll.mockResolvedValue([])
  recipesApi.delete = vi.fn().mockResolvedValue(null)

  render(<RecipesPage />)
  fireEvent.click(await screen.findByText('Risotto'))
  fireEvent.click(await screen.findByRole('button', { name: 'Delete' }))
  fireEvent.click(await screen.findByRole('button', { name: 'Cancel' }))

  expect(recipesApi.delete).not.toHaveBeenCalled()
  expect(screen.getByText('Risotto')).toBeInTheDocument()
})
```

- [ ] **Step 7: Run to verify they fail**

Run: `npm run test -- RecipesPage`
Expected: FAIL — no button named "Delete recipe", and the cancel test finds no "Cancel".

- [ ] **Step 8: Wire it into the page**

In `src/pages/RecipesPage.jsx`, add `ConfirmModal` to the barrel import from `'../components'`.

Add state beside the others:

```jsx
const [confirmingDelete, setConfirmingDelete] = React.useState(false)
```

Reset it whenever the open recipe changes, in the existing effect that clears `sharing`:

```jsx
React.useEffect(() => {
  setSharing(false)
  setConfirmingDelete(false)
}, [opened])
```

Replace the detail modal's action row. Share and Edit lose `size="sm"` so they reach the 44px default; Delete moves to its own row, separated by a rule:

```jsx
<div className="flex justify-end gap-2">
  <Button variant="secondary" onClick={() => setSharing(true)}>
    Share
  </Button>
  <Button
    variant="accent"
    onClick={() => {
      setEditing(openRecipe)
      setShowModal(true)
      setOpened(null)
    }}
  >
    Edit
  </Button>
</div>
<div
  className="mt-1 border-t pt-3"
  style={{ borderColor: 'var(--border-default)' }}
>
  <Button
    variant="ghost"
    className="w-full"
    style={{ color: 'var(--c-neg)' }}
    onClick={() => setConfirmingDelete(true)}
  >
    Delete
  </Button>
</div>
```

Then render the confirmation, inside the `{openRecipe && (...)}` block that already holds `ShareRecipeModal`, or as its own sibling block:

```jsx
{openRecipe && confirmingDelete && (
  <ConfirmModal
    title={`Delete ${openRecipe.title}?`}
    message="This can't be undone."
    confirmLabel="Delete recipe"
    onConfirm={() => {
      setConfirmingDelete(false)
      handleDelete(openRecipe.id)
    }}
    onCancel={() => setConfirmingDelete(false)}
  />
)}
```

The confirm button says "Delete recipe" rather than "Delete" so it is distinguishable from the trigger by accessible name — which is what makes the test above unambiguous, and what a screen-reader user hears too.

- [ ] **Step 9: Run to verify they pass**

Run: `npm run test -- RecipesPage`
Expected: PASS, all tests in the file.

- [ ] **Step 10: Commit**

```bash
git add src/components/ConfirmModal.jsx src/components/__tests__/ConfirmModal.test.jsx src/components/index.js src/pages/RecipesPage.jsx src/pages/__tests__/RecipesPage.test.jsx
git commit -m "Guard the recipe delete behind a confirmation

Delete was a 36px button beside Edit that called the API immediately,
with no undo path -- the one destructive action in the app, on the
smallest target it offers. It now sits on its own row below a rule and
asks first. Share and Edit lose size=sm and reach the 44px floor."
```

---

## Task 4: Extract the filter groups as chips

Both the mobile sheet (Task 6) and the desktop popover need the same three groups. Extracting them first means the two surfaces cannot drift, and replaces the 16px native checkboxes with 44px chips everywhere.

**Files:**
- Create: `src/components/RecipeFilters.jsx`
- Modify: `src/components/index.js`, `src/pages/RecipesPage.jsx`
- Test: `src/pages/__tests__/RecipesPage.test.jsx`

- [ ] **Step 1: Write the failing test**

The two existing filter tests click `screen.getByLabelText('Filter')` and then a checkbox label. Append a new test asserting the chip is a button at the touch floor:

```jsx
test('filter options are buttons, not sub-floor checkboxes', async () => {
  recipesApi.fetchAll.mockResolvedValue([
    { id: 1, title: 'Spaghetti', course: 'main', tags: ['quick'], ingredients: [] },
  ])
  tagsApi.fetchAll.mockResolvedValue([{ name: 'quick' }])
  ingredientsApi.fetchAll.mockResolvedValue([])

  render(<RecipesPage />)
  await screen.findByText('Spaghetti')
  fireEvent.click(screen.getByLabelText('Filter'))
  fireEvent.click(screen.getByRole('button', { name: 'Tags' }))

  const chip = screen.getByRole('button', { name: 'quick' })
  expect(chip).toHaveAttribute('aria-pressed', 'false')

  fireEvent.click(chip)
  expect(screen.getByRole('button', { name: 'quick' })).toHaveAttribute(
    'aria-pressed',
    'true',
  )
})
```

- [ ] **Step 2: Run to verify it fails**

Run: `npm run test -- RecipesPage`
Expected: FAIL — the options are `<input type="checkbox">` inside labels, so `getByRole('button', { name: 'quick' })` finds nothing.

- [ ] **Step 3: Implement**

Create `src/components/RecipeFilters.jsx`:

```jsx
import React from 'react'
import { ChevronDownIcon } from '@heroicons/react/24/outline'

/**
 * The three recipe filter groups — course, tags, ingredients — as collapsible
 * sets of toggle chips.
 *
 * Shared by the mobile bottom sheet and the desktop popover so the two
 * surfaces cannot drift apart. Chips rather than the native checkboxes that
 * were here before: a 13px checkbox is a third of the 44px target design
 * guide §8.4 requires, and three of them nested their own scroll areas inside
 * a popover inside the page scroll.
 *
 * `groups` is `[{ label, options, selected, onSelect }]`.
 */
export default function RecipeFilters({ groups }) {
  const [openLabel, setOpenLabel] = React.useState(null)

  return (
    <div className="flex flex-col gap-2">
      {groups.map(({ label, options, selected, onSelect }) => {
        const open = openLabel === label
        return (
          <div key={label}>
            <button
              type="button"
              aria-expanded={open}
              onClick={() => setOpenLabel(open ? null : label)}
              className="flex min-h-11 w-full items-center justify-between text-sm font-medium"
              style={{ color: 'var(--text-strong)' }}
            >
              {label}
              {selected.length > 0 && (
                <span
                  className="ml-auto mr-2 text-xs"
                  style={{ color: 'var(--text-subtle)' }}
                >
                  {selected.length}
                </span>
              )}
              <ChevronDownIcon
                className="h-4 w-4 transition-transform"
                style={{ transform: open ? 'rotate(180deg)' : undefined }}
              />
            </button>
            {open && (
              <div className="flex flex-wrap gap-2 pb-2">
                {options.map((option) => {
                  const active = selected.includes(option)
                  return (
                    <button
                      key={option}
                      type="button"
                      aria-pressed={active}
                      onClick={() => onSelect(option)}
                      className="min-h-11 rounded-full border px-4 text-sm"
                      style={{
                        borderColor: active ? 'var(--c-a2)' : 'var(--border-default)',
                        backgroundColor: active
                          ? 'color-mix(in srgb, var(--c-a2) 14%, transparent)'
                          : 'transparent',
                        color: active ? 'var(--c-a2)' : 'var(--text-strong)',
                      }}
                    >
                      {option}
                    </button>
                  )
                })}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}
```

`ToggleChip` is deliberately not reused here: it is `px-2.5 py-1 text-xs` with no minimum height, sized for dense inline rows, and raising it to 44px would change every other place it appears.

- [ ] **Step 4: Export it**

Add to `src/components/index.js`:

```js
export { default as RecipeFilters } from './RecipeFilters'
```

- [ ] **Step 5: Use it in the page**

In `src/pages/RecipesPage.jsx`, add `RecipeFilters` to the barrel import. Build the group list once, beside the other memos:

```jsx
const filterGroups = React.useMemo(
  () => [
    { label: 'Course', options: courseOptions, selected: selectedCourses, onSelect: toggleCourse },
    { label: 'Tags', options: tags, selected: selectedTags, onSelect: toggleTag },
    { label: 'Ingredients', options: ingredientNames, selected: selectedIngredients, onSelect: toggleIngredient },
  ],
  [courseOptions, selectedCourses, tags, selectedTags, ingredientNames, selectedIngredients],
)
```

Replace the three `<FilterGroup .../>` elements inside the popover with:

```jsx
<RecipeFilters groups={filterGroups} />
```

Delete the now-unused `FilterGroup` function at the bottom of the file, and drop `ChevronDownIcon` from the page's heroicons import if nothing else uses it.

- [ ] **Step 6: Run to verify it passes**

Run: `npm run test -- RecipesPage`
Expected: FAIL on the two *older* filter tests, which click checkbox labels that no longer exist. Update them: replace each

```jsx
fireEvent.click(screen.getByLabelText('Tomato'))
```

style line with the group-then-chip pair, e.g.

```jsx
fireEvent.click(screen.getByRole('button', { name: 'Ingredients' }))
fireEvent.click(screen.getByRole('button', { name: 'Tomato' }))
```

Read each existing test and adapt it to open the right group first. Then rerun.

Run: `npm run test -- RecipesPage`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/components/RecipeFilters.jsx src/components/index.js src/pages/RecipesPage.jsx src/pages/__tests__/RecipesPage.test.jsx
git commit -m "Turn the recipe filters into chips in a shared component

The options were 13px native checkboxes -- a third of the 44px floor --
in three nested scroll areas. They are now toggle chips at the floor, in
one component the coming mobile sheet and the desktop popover both use,
so the two surfaces cannot drift."
```

---

## Task 5: Active-filter chips, the count badge, and popover dismissal

A closed popover leaves a filtered grid with no explanation, at every width. The popover also cannot be dismissed by tapping away or pressing Esc, though `DateRangePicker` in this same codebase already does both.

**Files:**
- Create: `src/components/ActiveFilterChips.jsx`
- Modify: `src/components/index.js`, `src/pages/RecipesPage.jsx`
- Test: `src/pages/__tests__/RecipesPage.test.jsx`

- [ ] **Step 1: Write the failing tests**

```jsx
test('the funnel counts the active filters', async () => {
  recipesApi.fetchAll.mockResolvedValue([
    { id: 1, title: 'Spaghetti', course: 'main', tags: ['quick'], ingredients: [] },
  ])
  tagsApi.fetchAll.mockResolvedValue([{ name: 'quick' }])
  ingredientsApi.fetchAll.mockResolvedValue([])

  render(<RecipesPage />)
  await screen.findByText('Spaghetti')

  // jest-dom's toHaveTextContent('') matches anything, so assert the negative
  // against the value that will appear rather than against emptiness.
  expect(screen.getByLabelText('Filter')).not.toHaveTextContent('1')

  fireEvent.click(screen.getByLabelText('Filter'))
  fireEvent.click(screen.getByRole('button', { name: 'Tags' }))
  fireEvent.click(screen.getByRole('button', { name: 'quick' }))

  expect(screen.getByLabelText('Filter')).toHaveTextContent('1')
})

test('an active filter shows as a removable chip', async () => {
  recipesApi.fetchAll.mockResolvedValue([
    { id: 1, title: 'Spaghetti', course: 'main', tags: ['quick'], ingredients: [] },
    { id: 2, title: 'Pizza', course: 'main', tags: [], ingredients: [] },
  ])
  tagsApi.fetchAll.mockResolvedValue([{ name: 'quick' }])
  ingredientsApi.fetchAll.mockResolvedValue([])

  render(<RecipesPage />)
  await screen.findByText('Spaghetti')
  fireEvent.click(screen.getByLabelText('Filter'))
  fireEvent.click(screen.getByRole('button', { name: 'Tags' }))
  fireEvent.click(screen.getByRole('button', { name: 'quick' }))

  expect(screen.queryByText('Pizza')).toBeNull()

  fireEvent.click(screen.getByRole('button', { name: 'Remove filter quick' }))

  expect(await screen.findByText('Pizza')).toBeInTheDocument()
})

test('clear all drops every filter at once', async () => {
  recipesApi.fetchAll.mockResolvedValue([
    { id: 1, title: 'Spaghetti', course: 'main', tags: ['quick'], ingredients: [] },
    { id: 2, title: 'Pizza', course: 'first-course', tags: [], ingredients: [] },
  ])
  tagsApi.fetchAll.mockResolvedValue([{ name: 'quick' }])
  ingredientsApi.fetchAll.mockResolvedValue([])

  render(<RecipesPage />)
  await screen.findByText('Spaghetti')
  fireEvent.click(screen.getByLabelText('Filter'))
  fireEvent.click(screen.getByRole('button', { name: 'Tags' }))
  fireEvent.click(screen.getByRole('button', { name: 'quick' }))
  fireEvent.click(screen.getByRole('button', { name: 'Course' }))
  fireEvent.click(screen.getByRole('button', { name: 'main' }))

  fireEvent.click(screen.getByRole('button', { name: 'Clear all filters' }))

  expect(await screen.findByText('Pizza')).toBeInTheDocument()
  expect(screen.getByLabelText('Filter')).not.toHaveTextContent('2')
})

test('Escape closes the filter popover', async () => {
  recipesApi.fetchAll.mockResolvedValue([
    { id: 1, title: 'Spaghetti', course: 'main', tags: [], ingredients: [] },
  ])
  tagsApi.fetchAll.mockResolvedValue([])
  ingredientsApi.fetchAll.mockResolvedValue([])

  render(<RecipesPage />)
  await screen.findByText('Spaghetti')
  fireEvent.click(screen.getByLabelText('Filter'))
  expect(screen.getByRole('button', { name: 'Course' })).toBeInTheDocument()

  fireEvent.keyDown(document, { key: 'Escape' })

  await waitFor(() =>
    expect(screen.queryByRole('button', { name: 'Course' })).toBeNull(),
  )
})
```

- [ ] **Step 2: Run to verify they fail**

Run: `npm run test -- RecipesPage`
Expected: FAIL — no count on the funnel, no "Remove filter quick", no "Clear all filters", Escape does nothing.

- [ ] **Step 3: Implement the chip row**

Create `src/components/ActiveFilterChips.jsx`:

```jsx
import React from 'react'
import { XMarkIcon } from '@heroicons/react/24/outline'

/**
 * The filters currently narrowing the grid, each removable, plus a clear-all.
 *
 * Without this the only cue that a filter is on is the grid being short --
 * and once the popover or sheet is closed there is nothing on screen to say
 * why. Renders nothing when no filter is active.
 *
 * `filters` is `[{ value, onRemove }]`.
 */
export default function ActiveFilterChips({ filters, onClearAll }) {
  if (filters.length === 0) return null

  return (
    <div className="flex flex-wrap items-center gap-2">
      {filters.map(({ value, onRemove }) => (
        <button
          key={value}
          type="button"
          aria-label={`Remove filter ${value}`}
          onClick={onRemove}
          className="inline-flex min-h-9 items-center gap-1 rounded-full border px-3 text-xs"
          style={{
            borderColor: 'var(--border-default)',
            color: 'var(--text-strong)',
          }}
        >
          {value}
          <XMarkIcon className="h-3.5 w-3.5" aria-hidden="true" />
        </button>
      ))}
      <button
        type="button"
        aria-label="Clear all filters"
        onClick={onClearAll}
        className="min-h-9 px-2 text-xs underline"
        style={{ color: 'var(--c-neg)' }}
      >
        Clear all
      </button>
    </div>
  )
}
```

- [ ] **Step 4: Export it**

```js
export { default as ActiveFilterChips } from './ActiveFilterChips'
```

- [ ] **Step 5: Wire the page**

In `src/pages/RecipesPage.jsx`, add `ActiveFilterChips` to the barrel import and `React.useRef` usage for the popover.

Derive the active list from the same `filterGroups` already built in Task 4, so a new group can never be forgotten here:

```jsx
const activeFilters = React.useMemo(
  () =>
    filterGroups.flatMap(({ selected, onSelect }) =>
      selected.map((value) => ({ value, onRemove: () => onSelect(value) })),
    ),
  [filterGroups],
)

const clearAllFilters = () => {
  setSelectedCourses([])
  setSelectedTags([])
  setSelectedIngredients([])
}
```

Add the count to the funnel. The `Button` currently used for it is replaced by an `IconButton` wrapped in the existing `relative` div, so the badge can be positioned:

```jsx
<div className="relative" ref={filterRef}>
  <IconButton
    Icon={FunnelIcon}
    label="Filter"
    data-tour="recipes-filter"
    onClick={() => setShowFilters((s) => !s)}
    className="border"
    style={{ borderColor: 'var(--border-default)', borderRadius: 'var(--radius-md)' }}
  />
  {activeFilters.length > 0 && (
    <span
      aria-hidden="true"
      className="pointer-events-none absolute -right-1 -top-1 flex h-5 min-w-5 items-center justify-center rounded-full px-1 text-xs"
      style={{ backgroundColor: 'var(--c-neg)', color: '#fff' }}
    >
      {activeFilters.length}
    </span>
  )}
  {showFilters && ( /* the popover, unchanged from Task 4 */ )}
</div>
```

The badge is `aria-hidden` and the count reaches assistive tech through the button's own text content, which is why the test asserts `toHaveTextContent('1')` on the button rather than querying the span.

Add dismissal, copying the pattern `DateRangePicker` already uses:

```jsx
const filterRef = React.useRef(null)

React.useEffect(() => {
  if (!showFilters) return undefined
  const onDown = (e) => {
    if (filterRef.current && !filterRef.current.contains(e.target)) setShowFilters(false)
  }
  const onKey = (e) => {
    if (e.key === 'Escape') setShowFilters(false)
  }
  document.addEventListener('mousedown', onDown)
  document.addEventListener('keydown', onKey)
  return () => {
    document.removeEventListener('mousedown', onDown)
    document.removeEventListener('keydown', onKey)
  }
}, [showFilters])
```

Render the chip row directly beneath the header row, above the grid:

```jsx
<ActiveFilterChips filters={activeFilters} onClearAll={clearAllFilters} />
```

- [ ] **Step 6: Run to verify they pass**

Run: `npm run test -- RecipesPage`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/components/ActiveFilterChips.jsx src/components/index.js src/pages/RecipesPage.jsx src/pages/__tests__/RecipesPage.test.jsx
git commit -m "Make an active recipe filter visible, removable and escapable

A closed popover left a short grid with nothing on screen explaining why.
The funnel now carries a count, active filters show as removable chips
with a clear-all, and the popover finally dismisses on outside-click and
Escape -- the pattern DateRangePicker already implements two files away."
```

---

## Task 6: `BottomSheet`

**Files:**
- Create: `src/components/BottomSheet.jsx`, `src/components/__tests__/BottomSheet.test.jsx`
- Modify: `src/components/index.js`

- [ ] **Step 1: Write the failing test**

Create `src/components/__tests__/BottomSheet.test.jsx`:

```jsx
/**
 * @vitest-environment jsdom
 */
import React from 'react'
import { render, screen, fireEvent, cleanup } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import '@testing-library/jest-dom/vitest'
import BottomSheet from '../BottomSheet'

afterEach(() => cleanup())

test('renders its title and children', () => {
  render(
    <BottomSheet title="Filters" onClose={() => {}}>
      <p>body</p>
    </BottomSheet>,
  )

  expect(screen.getByText('Filters')).toBeInTheDocument()
  expect(screen.getByText('body')).toBeInTheDocument()
})

test('Escape closes it', () => {
  const onClose = vi.fn()
  render(
    <BottomSheet title="Filters" onClose={onClose}>
      <p>body</p>
    </BottomSheet>,
  )

  fireEvent.keyDown(document, { key: 'Escape' })

  expect(onClose).toHaveBeenCalledTimes(1)
})

test('the close control is reachable by name', () => {
  const onClose = vi.fn()
  render(
    <BottomSheet title="Filters" onClose={onClose}>
      <p>body</p>
    </BottomSheet>,
  )

  fireEvent.click(screen.getByRole('button', { name: 'Close' }))

  expect(onClose).toHaveBeenCalledTimes(1)
})

test('a click inside the sheet does not close it', () => {
  const onClose = vi.fn()
  render(
    <BottomSheet title="Filters" onClose={onClose}>
      <p>body</p>
    </BottomSheet>,
  )

  fireEvent.click(screen.getByText('body'))

  expect(onClose).not.toHaveBeenCalled()
})
```

- [ ] **Step 2: Run to verify it fails**

Run: `npm run test -- BottomSheet`
Expected: FAIL — "Failed to resolve import ../BottomSheet".

- [ ] **Step 3: Implement**

Create `src/components/BottomSheet.jsx`:

```jsx
import React from 'react'
import { XMarkIcon } from '@heroicons/react/24/outline'
import { IconButton } from './IconButton'
import { SCRIM, Z } from '../lib/layers'

/**
 * A panel anchored to the bottom of the viewport.
 *
 * `ModalScrim` centers its child, which is right for a dialog and wrong for a
 * sheet, so this lays out its own wash with `alignItems: flex-end` rather than
 * fighting it -- but takes `SCRIM` and `Z` from the same module so the wash
 * colour and the stacking order stay in one place.
 *
 * Bottom-anchored because a phone's thumb reaches the bottom of the screen and
 * not the top: the controls in here are the ones being used repeatedly.
 * `footer` is pinned below the scrolling body so a primary action stays put
 * however long the content is.
 */
export default function BottomSheet({ title, onClose, footer, children }) {
  React.useEffect(() => {
    const onKey = (e) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div
      onClick={onClose}
      style={{
        position: 'fixed',
        inset: 0,
        backgroundColor: SCRIM,
        display: 'flex',
        alignItems: 'flex-end',
        zIndex: Z.modal,
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onClick={(e) => e.stopPropagation()}
        className="flex w-full flex-col bg-white"
        style={{
          borderTopLeftRadius: 'var(--radius-lg)',
          borderTopRightRadius: 'var(--radius-lg)',
          maxHeight: '85vh',
          paddingBottom: 'env(safe-area-inset-bottom)',
        }}
      >
        <div className="flex items-center justify-between px-4 pt-2">
          <h3
            style={{
              margin: 0,
              fontSize: 'var(--text-lg)',
              fontWeight: 'var(--weight-semibold)',
              color: 'var(--text-strong)',
            }}
          >
            {title}
          </h3>
          <IconButton Icon={XMarkIcon} label="Close" onClick={onClose} />
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto px-4 pb-2">{children}</div>
        {footer && (
          <div
            className="border-t px-4 py-3"
            style={{ borderColor: 'var(--border-default)' }}
          >
            {footer}
          </div>
        )}
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Export it**

```js
export { default as BottomSheet } from './BottomSheet'
```

- [ ] **Step 5: Run to verify it passes**

Run: `npm run test -- BottomSheet`
Expected: PASS, 4 tests.

- [ ] **Step 6: Commit**

```bash
git add src/components/BottomSheet.jsx src/components/__tests__/BottomSheet.test.jsx src/components/index.js
git commit -m "Add a BottomSheet primitive

A bottom-anchored panel for the controls a thumb reaches often. Lays out
its own wash because ModalScrim centers its child, but shares SCRIM and Z
so the colour and stacking order stay in one place."
```

---

## Task 7: Filters open in the sheet on mobile

**Files:**
- Modify: `src/pages/RecipesPage.jsx`
- Test: `src/pages/__tests__/RecipesPage.test.jsx`

- [ ] **Step 1: Write the failing tests**

```jsx
test('the filter opens a bottom sheet on mobile', async () => {
  stubViewport(true)
  recipesApi.fetchAll.mockResolvedValue([
    { id: 1, title: 'Spaghetti', course: 'main', tags: [], ingredients: [] },
  ])
  tagsApi.fetchAll.mockResolvedValue([])
  ingredientsApi.fetchAll.mockResolvedValue([])

  render(<RecipesPage />)
  await screen.findByText('Spaghetti')
  fireEvent.click(screen.getByLabelText('Filter'))

  expect(screen.getByRole('dialog', { name: 'Filters' })).toBeInTheDocument()
})

test('the filter stays a popover on desktop', async () => {
  stubViewport(false)
  recipesApi.fetchAll.mockResolvedValue([
    { id: 1, title: 'Spaghetti', course: 'main', tags: [], ingredients: [] },
  ])
  tagsApi.fetchAll.mockResolvedValue([])
  ingredientsApi.fetchAll.mockResolvedValue([])

  render(<RecipesPage />)
  await screen.findByText('Spaghetti')
  fireEvent.click(screen.getByLabelText('Filter'))

  expect(screen.queryByRole('dialog', { name: 'Filters' })).toBeNull()
  expect(screen.getByRole('button', { name: 'Course' })).toBeInTheDocument()
})

test('the sheet footer reports the filtered count and closes the sheet', async () => {
  stubViewport(true)
  recipesApi.fetchAll.mockResolvedValue([
    { id: 1, title: 'Spaghetti', course: 'main', tags: [], ingredients: [] },
    { id: 2, title: 'Pizza', course: 'main', tags: [], ingredients: [] },
  ])
  tagsApi.fetchAll.mockResolvedValue([])
  ingredientsApi.fetchAll.mockResolvedValue([])

  render(<RecipesPage />)
  await screen.findByText('Spaghetti')
  fireEvent.click(screen.getByLabelText('Filter'))

  fireEvent.click(screen.getByRole('button', { name: 'Show 2 recipes' }))

  await waitFor(() =>
    expect(screen.queryByRole('dialog', { name: 'Filters' })).toBeNull(),
  )
})
```

- [ ] **Step 2: Run to verify they fail**

Run: `npm run test -- RecipesPage`
Expected: FAIL — no dialog named "Filters".

- [ ] **Step 3: Implement**

In `src/pages/RecipesPage.jsx`, add `BottomSheet` to the barrel import. Replace the single `{showFilters && (<div className="absolute ...">...</div>)}` block with a branch. The popover keeps its existing markup; the sheet reuses the same `RecipeFilters`:

```jsx
{showFilters && !isMobile && (
  <div
    className="absolute right-0 z-10 mt-2 w-[min(14rem,calc(100vw-2rem))] rounded-2xl border bg-white p-2"
    style={{ borderColor: 'var(--border-default)' }}
  >
    <RecipeFilters groups={filterGroups} />
  </div>
)}
```

And, outside the `relative` wrapper (a `position: fixed` sheet must not be nested inside it), beside the other modals at the bottom of the page:

```jsx
{showFilters && isMobile && (
  <BottomSheet
    title="Filters"
    onClose={() => setShowFilters(false)}
    footer={
      <Button
        variant="accent"
        className="w-full"
        onClick={() => setShowFilters(false)}
      >
        {`Show ${filteredRecipes.length} ${
          filteredRecipes.length === 1 ? 'recipe' : 'recipes'
        }`}
      </Button>
    }
  >
    <RecipeFilters groups={filterGroups} />
  </BottomSheet>
)}
```

The outside-click effect from Task 5 must not fight the sheet, which has its own backdrop. Guard it:

```jsx
React.useEffect(() => {
  if (!showFilters || isMobile) return undefined
  // ...unchanged
}, [showFilters, isMobile])
```

- [ ] **Step 4: Run to verify they pass**

Run: `npm run test -- RecipesPage`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/pages/RecipesPage.jsx src/pages/__tests__/RecipesPage.test.jsx
git commit -m "Open the recipe filters in a bottom sheet below md

Three nested scroll areas in a 224px popover become one scroll region in
a thumb-reachable sheet, with a footer stating what the current selection
will show. Desktop keeps the popover; both render the same RecipeFilters."
```

---

## Task 8: The FAB, the create sheet, and the mobile header

The reported bug. Four controls share a non-wrapping row; the search input cannot shrink, so the two text buttons starve and wrap their labels, which is also why they end up taller than the funnel beside them.

**Files:**
- Create: `src/components/Fab.jsx`, `src/components/__tests__/Fab.test.jsx`
- Modify: `src/components/index.js`, `src/pages/RecipesPage.jsx`, `src/tutorial/steps.js`
- Test: `src/pages/__tests__/RecipesPage.test.jsx`

- [ ] **Step 1: Write the failing `Fab` test**

Create `src/components/__tests__/Fab.test.jsx`:

```jsx
/**
 * @vitest-environment jsdom
 */
import React from 'react'
import { render, screen, fireEvent, cleanup } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import '@testing-library/jest-dom/vitest'
import { PlusIcon } from '@heroicons/react/24/outline'
import Fab from '../Fab'

afterEach(() => cleanup())

test('is reachable by its accessible name and calls onClick', () => {
  const onClick = vi.fn()
  render(<Fab Icon={PlusIcon} label="Add a recipe" onClick={onClick} />)

  fireEvent.click(screen.getByRole('button', { name: 'Add a recipe' }))

  expect(onClick).toHaveBeenCalledTimes(1)
})
```

- [ ] **Step 2: Run to verify it fails**

Run: `npm run test -- Fab`
Expected: FAIL — "Failed to resolve import ../Fab".

- [ ] **Step 3: Implement `Fab`**

Create `src/components/Fab.jsx`:

```jsx
import React from 'react'
import { Z } from '../lib/layers'

/**
 * The primary action of a page, floating in the bottom-right corner.
 *
 * 56px rather than the 44px floor: this is the one control a thumb goes for
 * without looking. It sits above `env(safe-area-inset-bottom)` so a home
 * indicator does not eat it, and below `Z.drawer` so the nav drawer and every
 * dialog still cover it.
 *
 * A page that renders one must pad the bottom of its scrolling content by at
 * least the button's height plus its offset, or the last row hides underneath.
 */
export default function Fab({ Icon, label, onClick, ...props }) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      onClick={onClick}
      className="fixed flex h-14 w-14 items-center justify-center rounded-full shadow-lg"
      style={{
        right: 16,
        bottom: 'calc(16px + env(safe-area-inset-bottom))',
        backgroundColor: 'var(--c-a2)',
        color: 'var(--text-on-accent)',
        zIndex: Z.drawer - 1,
      }}
      {...props}
    >
      {Icon && <Icon className="h-7 w-7" />}
    </button>
  )
}
```

- [ ] **Step 4: Export it and verify**

```js
export { default as Fab } from './Fab'
```

Run: `npm run test -- Fab`
Expected: PASS.

- [ ] **Step 5: Write the failing page tests**

```jsx
test('the mobile header holds only search and filter', async () => {
  stubViewport(true)
  recipesApi.fetchAll.mockResolvedValue([
    { id: 1, title: 'Spaghetti', course: 'main', tags: [], ingredients: [] },
  ])
  tagsApi.fetchAll.mockResolvedValue([])
  ingredientsApi.fetchAll.mockResolvedValue([])

  render(<RecipesPage />)
  await screen.findByText('Spaghetti')

  expect(screen.queryByRole('button', { name: 'Import from web' })).toBeNull()
  expect(screen.queryByRole('button', { name: /^New recipe$/ })).toBeNull()
  expect(screen.getByLabelText('Filter')).toBeInTheDocument()
})

test('the mobile add button offers both ways to create a recipe', async () => {
  stubViewport(true)
  recipesApi.fetchAll.mockResolvedValue([
    { id: 1, title: 'Spaghetti', course: 'main', tags: [], ingredients: [] },
  ])
  tagsApi.fetchAll.mockResolvedValue([])
  ingredientsApi.fetchAll.mockResolvedValue([])

  render(<RecipesPage />)
  await screen.findByText('Spaghetti')

  fireEvent.click(screen.getByRole('button', { name: 'Add a recipe' }))

  expect(
    screen.getByRole('button', { name: 'Write it myself' }),
  ).toBeInTheDocument()
  expect(
    screen.getByRole('button', { name: 'Import from a website' }),
  ).toBeInTheDocument()
})

test('the add sheet opens the import dialog', async () => {
  stubViewport(true)
  recipesApi.fetchAll.mockResolvedValue([
    { id: 1, title: 'Spaghetti', course: 'main', tags: [], ingredients: [] },
  ])
  tagsApi.fetchAll.mockResolvedValue([])
  ingredientsApi.fetchAll.mockResolvedValue([])

  render(<RecipesPage />)
  await screen.findByText('Spaghetti')

  fireEvent.click(screen.getByRole('button', { name: 'Add a recipe' }))
  fireEvent.click(screen.getByRole('button', { name: 'Import from a website' }))

  // The add sheet gives way to the import dialog rather than stacking.
  await waitFor(() =>
    expect(screen.queryByRole('button', { name: 'Write it myself' })).toBeNull(),
  )
})

test('desktop keeps both header buttons', async () => {
  stubViewport(false)
  recipesApi.fetchAll.mockResolvedValue([
    { id: 1, title: 'Spaghetti', course: 'main', tags: [], ingredients: [] },
  ])
  tagsApi.fetchAll.mockResolvedValue([])
  ingredientsApi.fetchAll.mockResolvedValue([])

  render(<RecipesPage />)
  await screen.findByText('Spaghetti')

  expect(
    screen.getByRole('button', { name: 'Import from web' }),
  ).toBeInTheDocument()
  expect(screen.getByRole('button', { name: /New recipe/ })).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Add a recipe' })).toBeNull()
})
```

- [ ] **Step 6: Run to verify they fail**

Run: `npm run test -- RecipesPage`
Expected: FAIL — no button named "Add a recipe".

- [ ] **Step 7: Implement the header branch**

In `src/pages/RecipesPage.jsx`, add `Fab` to the barrel import and add state:

```jsx
const [showAddSheet, setShowAddSheet] = React.useState(false)
```

Give the search `Input` a shrinkable width. `min-w-0` is the missing piece: without it a flex item refuses to go below its content width, which is what makes the row unsqueezable:

```jsx
<Input
  placeholder="Search recipes…"
  data-tour="recipes-search"
  className="min-w-0 flex-1 md:w-56 md:flex-none"
  value={search}
  onChange={(e) => setSearch(e.target.value)}
/>
```

Wrap the two text buttons so they only render at md and above:

```jsx
{!isMobile && (
  <>
    <Button
      variant="ghost"
      data-tour="recipes-import"
      className="whitespace-nowrap"
      onClick={() => setShowImport(true)}
    >
      Import from web
    </Button>
    <Button
      variant="accent"
      data-tour="recipes-new"
      Icon={PlusIcon}
      className="whitespace-nowrap"
      onClick={() => {
        setEditing(null)
        setShowModal(true)
      }}
    >
      New recipe
    </Button>
  </>
)}
```

`whitespace-nowrap` is belt and braces for the desktop row: nothing should starve there now, but a label that wraps is what produced the unequal heights, and this makes it impossible rather than unlikely.

Also give the header's inner cluster `flex-wrap` so it degrades rather than overflowing at any width the branch does not cover:

```jsx
<div className="flex flex-wrap items-center gap-2">
```

Add the FAB and its sheet at the bottom of the returned tree, beside the other modals:

```jsx
{isMobile && (
  <Fab
    Icon={PlusIcon}
    label="Add a recipe"
    data-tour="recipes-new"
    onClick={() => setShowAddSheet(true)}
  />
)}

{showAddSheet && (
  <BottomSheet title="Add a recipe" onClose={() => setShowAddSheet(false)}>
    <div className="flex flex-col gap-2 pb-2">
      <Button
        variant="accent"
        Icon={PencilSquareIcon}
        className="w-full justify-start"
        onClick={() => {
          setShowAddSheet(false)
          setEditing(null)
          setShowModal(true)
        }}
      >
        Write it myself
      </Button>
      <Button
        variant="ghost"
        Icon={GlobeAltIcon}
        className="w-full justify-start"
        data-tour="recipes-import"
        onClick={() => {
          setShowAddSheet(false)
          setShowImport(true)
        }}
      >
        Import from a website
      </Button>
    </div>
  </BottomSheet>
)}
```

Extend the heroicons import at the top of the file:

```jsx
import {
  FunnelIcon,
  PlusIcon,
  PencilSquareIcon,
  GlobeAltIcon,
} from '@heroicons/react/24/outline'
```

Pad the grid so the FAB never covers the last row — 56px button plus its 16px offset plus breathing room:

```jsx
<div data-tour="recipes-grid" className="card-grid pb-24 md:pb-0">
```

- [ ] **Step 8: Run to verify they pass**

Run: `npm run test -- RecipesPage`
Expected: PASS.

- [ ] **Step 9: Check the tour still has anchors**

The `data-tour` values `recipes-new` and `recipes-import` are targeted by `src/tutorial/steps.js`. On mobile both now live on elements that exist only conditionally: `recipes-new` on the FAB (always mounted on mobile — fine), `recipes-import` inside the add sheet (mounted only while the sheet is open — **not** fine).

Give the import step a fallback anchor, using the array form `steps.js` already supports (see the `recipes-card` step, which passes `['[data-tour="recipes-card"]', '[data-tour="recipes-grid"]']`):

```js
{
  target: ['[data-tour="recipes-import"]', '[data-tour="recipes-new"]'],
  title: 'Or let a chatbot do the typing',
  body: 'Copy the prompt you get here into any chatbot, along with the recipe, and paste back the JSON it returns — ingredients and all.',
  placement: 'bottom',
},
```

Run: `npm run test`
Expected: PASS, whole suite.

- [ ] **Step 10: Commit**

```bash
git add -A
git commit -m "Replace the crowded Recipes header with a search row and a FAB

Four controls shared a flex row with no wrap, and the search input had no
min-w-0 so it could not shrink -- the two text buttons starved and wrapped
their labels, which is also why they ended up taller than the funnel next
to them. Below md the row is now search plus filter, and both creation
paths live behind a floating + that opens a two-choice sheet. Desktop is
unchanged apart from whitespace-nowrap on the two buttons."
```

---

## Task 9: Recipes empty states

**Files:**
- Modify: `src/pages/RecipesPage.jsx`
- Test: `src/pages/__tests__/RecipesPage.test.jsx`

- [ ] **Step 1: Write the failing test**

```jsx
test('says so when no recipe matches the filters', async () => {
  recipesApi.fetchAll.mockResolvedValue([
    { id: 1, title: 'Spaghetti', course: 'main', tags: [], ingredients: [] },
  ])
  tagsApi.fetchAll.mockResolvedValue([])
  ingredientsApi.fetchAll.mockResolvedValue([])

  render(<RecipesPage />)
  await screen.findByText('Spaghetti')

  fireEvent.change(screen.getByPlaceholderText('Search recipes…'), {
    target: { value: 'zzz' },
  })

  expect(screen.getByText('No recipes match your search.')).toBeInTheDocument()
})
```

- [ ] **Step 2: Run to verify it fails**

Run: `npm run test -- RecipesPage`
Expected: FAIL — text not found.

- [ ] **Step 3: Implement**

Directly after the grid `div` in `src/pages/RecipesPage.jsx`:

```jsx
{loaded && recipes.length > 0 && filteredRecipes.length === 0 && (
  <div
    className="flex flex-col items-center gap-3 py-12 text-center"
    style={{ color: 'var(--text-subtle)' }}
  >
    <p style={{ margin: 0, fontSize: 'var(--text-sm)' }}>
      No recipes match your search.
    </p>
    {activeFilters.length > 0 && (
      <Button variant="ghost" onClick={clearAllFilters}>
        Clear all filters
      </Button>
    )}
  </div>
)}
```

The `recipes.length > 0` guard keeps this out of the way of a brand-new account, which gets the starter-pack modal instead — two empty states firing at once would be worse than none.

- [ ] **Step 4: Run to verify it passes**

Run: `npm run test -- RecipesPage`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/pages/RecipesPage.jsx src/pages/__tests__/RecipesPage.test.jsx
git commit -m "Explain an empty recipe grid instead of showing nothing

A search or filter that matches nothing rendered a blank page with no
clue whether it was still loading. Held back on a brand-new account,
which already gets the starter-pack offer."
```

---

## Task 10: Shopping list — one month on mobile, wrapping header

**Files:**
- Modify: `src/pages/ShoppingListPage.jsx`
- Test: `src/pages/__tests__/ShoppingListPage.test.jsx`

- [ ] **Step 1: Write the failing tests**

Add to `src/pages/__tests__/ShoppingListPage.test.jsx`. It does not yet import `stubViewport`; add it:

```jsx
import { stubViewport } from '../../test/stubViewport'
```

`MonthGrid` renders no landmark of its own, so the test counts rendered month grids by giving the wrapper a test id in Step 3.

```jsx
test('shows a single month on mobile', async () => {
  stubViewport(true)
  render(<ShoppingListPage />)
  await screen.findByText('A')

  expect(screen.getAllByTestId('shopping-month')).toHaveLength(1)
})

test('keeps three months on desktop', async () => {
  stubViewport(false)
  render(<ShoppingListPage />)
  await screen.findByText('A')

  expect(screen.getAllByTestId('shopping-month')).toHaveLength(3)
})
```

- [ ] **Step 2: Run to verify they fail**

Run: `npm run test -- ShoppingListPage`
Expected: FAIL — no elements with test id `shopping-month`.

- [ ] **Step 3: Implement**

In `src/pages/ShoppingListPage.jsx`, import the hook and call it:

```jsx
import { useIsMobile } from '../hooks/useIsMobile'
```

```jsx
const isMobile = useIsMobile()
```

Make the month count depend on the viewport. The calendar is read-only — it only tints a range the `DateRangePicker` above already states in words — so on a phone one month is confirmation enough and three cost two screens before any content:

```jsx
const months = React.useMemo(() => {
  if (!startDate) return []
  const base = new Date(startDate)
  const first = new Date(base.getFullYear(), base.getMonth(), 1)
  return Array.from({ length: isMobile ? 1 : 3 }, (_, i) => {
    const d = new Date(first)
    d.setMonth(first.getMonth() + i)
    return d
  })
}, [startDate, isMobile])
```

Add the test id, and replace the `sm:` basis with `md:` per the design guide's single dividing line:

```jsx
<div
  key={m.toISOString()}
  data-testid="shopping-month"
  className="flex basis-full justify-center md:basis-[30%]"
>
  <MonthGrid baseDate={m} startDate={start} endDate={end} />
</div>
```

Let the header controls wrap rather than overflow at 320px:

```jsx
<div className="flex flex-wrap items-end gap-2">
```

And change the `Card` wrapping the months from `px-4 py-4 sm:px-8 sm:py-6` to `px-4 py-4 md:px-8 md:py-6`.

- [ ] **Step 4: Run to verify they pass**

Run: `npm run test -- ShoppingListPage`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/pages/ShoppingListPage.jsx src/pages/__tests__/ShoppingListPage.test.jsx
git commit -m "Show one month, not three, on the mobile shopping list

The count was hardcoded at 3 in a container that goes full-width below
640px, so a phone got three stacked calendars -- roughly two screens
before any content. The grid is read-only: it only tints a range the
picker directly above already states in words."
```

---

## Task 11: Shopping list — Ingredients / Meals tabs on mobile

**Files:**
- Modify: `src/pages/ShoppingListPage.jsx`
- Test: `src/pages/__tests__/ShoppingListPage.test.jsx`

- [ ] **Step 1: Write the failing tests**

```jsx
test('mobile opens on the ingredients tab and hides the meal list', async () => {
  stubViewport(true)
  render(<ShoppingListPage />)

  expect(await screen.findByText('ing1: 2 kg')).toBeInTheDocument()
  // 'A' is a meal title, which lives on the other tab.
  expect(screen.queryByText('A')).toBeNull()
})

test('mobile can switch to the meal list', async () => {
  stubViewport(true)
  render(<ShoppingListPage />)
  await screen.findByText('ing1: 2 kg')

  fireEvent.click(screen.getByRole('button', { name: 'Meals' }))

  expect(await screen.findByText('A')).toBeInTheDocument()
  expect(screen.queryByText('ing1: 2 kg')).toBeNull()
})

test('desktop shows both lists at once and no tabs', async () => {
  stubViewport(false)
  render(<ShoppingListPage />)

  expect(await screen.findByText('A')).toBeInTheDocument()
  expect(screen.getByText('ing1: 2 kg')).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Meals' })).toBeNull()
})
```

`fireEvent` is not currently imported in this test file — add it to the `@testing-library/react` import.

- [ ] **Step 2: Run to verify they fail**

Run: `npm run test -- ShoppingListPage`
Expected: FAIL — both lists render on mobile; no button named "Meals".

- [ ] **Step 3: Implement**

In `src/pages/ShoppingListPage.jsx`, add `ViewToggle` to the barrel import and add state:

```jsx
// Ingredients first: it is the half you hold up in a shop.
const [tab, setTab] = React.useState('ingredients')
```

Extract the two existing `<Card>` blocks into local variables — `recipesCard` and `ingredientsCard` — containing exactly the JSX they hold today, then replace the wrapper `div` with:

```jsx
{isMobile ? (
  <div className="flex flex-col gap-3">
    <ViewToggle
      value={tab}
      onChange={setTab}
      options={[
        ['ingredients', 'Ingredients'],
        ['meals', 'Meals'],
      ]}
    />
    {tab === 'ingredients' ? ingredientsCard : recipesCard}
  </div>
) : (
  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
    {recipesCard}
    {ingredientsCard}
  </div>
)}
```

The desktop branch keeps the exact markup that is there today, including the source order (Recipes first), so nothing above md moves.

- [ ] **Step 4: Run to verify they pass**

Run: `npm run test -- ShoppingListPage`
Expected: PASS. The pre-existing tests in this file have no `stubViewport` call, so they run at jsdom's 1024px default and take the desktop branch, where both lists are present — they keep passing unchanged.

- [ ] **Step 5: Commit**

```bash
git add src/pages/ShoppingListPage.jsx src/pages/__tests__/ShoppingListPage.test.jsx
git commit -m "Split the mobile shopping list into Ingredients and Meals tabs

Stacked, up to fourteen meals sat above the ingredient list, so the half
you actually carry into a shop was two screens down. Ingredients is the
default tab. Desktop keeps both columns and shows no toggle."
```

---

## Task 12: Shopping list — the batch label stops stranding

**Files:**
- Modify: `src/pages/ShoppingListPage.jsx`
- Test: `src/pages/__tests__/ShoppingListPage.test.jsx`

- [ ] **Step 1: Write the failing test**

The existing test `an occurrence cooking part of a recipe says so` already asserts `×½` renders. What is missing is that the label flows with the title rather than being a sibling flex item. Assert the relationship:

```jsx
test('the batch label flows inline with the recipe title', async () => {
  const todayIso = new Date().toISOString().slice(0, 10)
  mealPlansApi.fetchRange.mockResolvedValue({
    [todayIso]: [
      { recipe: 'A', side_recipes: [], leftover: false, meal_number: 1, people: 2 },
    ],
  })
  recipesApi.fetchAll.mockResolvedValue([
    { id: 1, title: 'A', servings: 4, ingredients: [] },
  ])

  render(<ShoppingListPage />)

  const label = await screen.findByText('×½')
  // Same text flow as the title, not a separate flex item beside it.
  expect(label.parentElement).toHaveTextContent('A ×½')
  expect(label.parentElement.className).not.toMatch(/flex/)
})
```

- [ ] **Step 2: Run to verify it fails**

Run: `npm run test -- ShoppingListPage`
Expected: FAIL — the parent is `flex items-baseline gap-2`.

- [ ] **Step 3: Implement**

Replace the title block inside the meal `<li>`:

```jsx
<div>
  {o.mainTitle}
  {labels.main && (
    <span
      className="ml-2 text-xs tabular-nums"
      style={{ color: 'var(--text-subtle)' }}
    >
      {labels.main}
    </span>
  )}
</div>
```

A flex row makes the title and the label two unbreakable items, so a long title pushes the label onto its own unaligned line. As inline content the label simply follows the last word.

- [ ] **Step 4: Run to verify it passes**

Run: `npm run test -- ShoppingListPage`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/pages/ShoppingListPage.jsx src/pages/__tests__/ShoppingListPage.test.jsx
git commit -m "Let the batch label follow the recipe title instead of stranding

flex items-baseline made the title and the label two unbreakable items,
so a long title pushed the portion count onto its own unaligned line."
```

---

## Task 13: Shopping list — real tick boxes that respect a quantity change

**Files:**
- Modify: `src/pages/ShoppingListPage.jsx`
- Test: `src/pages/__tests__/ShoppingListPage.test.jsx`

- [ ] **Step 1: Write the failing tests**

```jsx
test('an ingredient row is a button that toggles pressed', async () => {
  render(<ShoppingListPage />)
  const row = await screen.findByRole('button', { name: /ing1: 2 kg/ })

  expect(row).toHaveAttribute('aria-pressed', 'false')

  fireEvent.click(row)

  expect(
    screen.getByRole('button', { name: /ing1: 2 kg/ }),
  ).toHaveAttribute('aria-pressed', 'true')
})

test('a ticked ingredient unticks when its quantity changes', async () => {
  render(<ShoppingListPage />)
  fireEvent.click(await screen.findByRole('button', { name: /ing1: 2 kg/ }))
  expect(
    screen.getByRole('button', { name: /ing1: 2 kg/ }),
  ).toHaveAttribute('aria-pressed', 'true')

  // Meal A goes from 2 people to 3, so ing1 becomes 3 kg.
  fireEvent.click(screen.getAllByRole('button', { name: 'More people' })[0])

  const row = await screen.findByRole('button', { name: /ing1: 3 kg/ })
  expect(row).toHaveAttribute('aria-pressed', 'false')
})

test('a quantity change leaves other ticks alone', async () => {
  render(<ShoppingListPage />)
  fireEvent.click(await screen.findByRole('button', { name: /ing2: 3 kg/ }))

  fireEvent.click(screen.getAllByRole('button', { name: 'More people' })[0])

  expect(
    await screen.findByRole('button', { name: /ing2: 3 kg/ }),
  ).toHaveAttribute('aria-pressed', 'true')
})

test('ticked items are left out of the export', async () => {
  // jsdom implements neither of these, so assign them rather than spying.
  URL.createObjectURL = vi.fn(() => 'blob:x')
  URL.revokeObjectURL = vi.fn()
  const blobSpy = vi.spyOn(globalThis, 'Blob')

  render(<ShoppingListPage />)
  fireEvent.click(await screen.findByRole('button', { name: /ing1: 2 kg/ }))
  fireEvent.click(screen.getByRole('button', { name: 'Export open items' }))

  const text = blobSpy.mock.calls[0][0][0]
  expect(text).not.toMatch(/ing1/)
  expect(text).toMatch(/ing2/)
})
```

- [ ] **Step 2: Run to verify they fail**

Run: `npm run test -- ShoppingListPage`
Expected: FAIL — the rows are `<li>`, so no button role.

- [ ] **Step 3: Implement the state change**

In `src/pages/ShoppingListPage.jsx`, change the declaration:

```jsx
// Ingredient key -> the amount that was on screen when it was ticked.
//
// Keying on the amount rather than just the key is what makes a head-count
// change untick the rows it actually affected: a row counts as ticked only
// while the amount still matches, so the invalidation is a render-time
// comparison rather than an effect that has to notice the change and go
// looking for stale entries.
const [crossed, setCrossed] = React.useState(() => new Map())
```

`handleLoad`'s reset becomes:

```jsx
setCrossed(new Map())
```

Add one helper beside the render, and use it in both the list and the export so they can never disagree:

```jsx
const isCrossedOff = (ing) => crossed.get(ing.key) === ing.amount
```

`handleExport`'s filter becomes:

```jsx
const items = ingredients
  .filter((ing) => !isCrossedOff(ing))
  .map(({ name, amount, unit }) => ({ name, amount, unit }))
```

- [ ] **Step 4: Implement the row**

Replace the ingredient `<li>` with a button inside it. `label` is unchanged, and stays a single text node so the existing `getByText('ing2: 3 kg')` assertions keep working:

```jsx
{ingredients.map((ing) => {
  const isCrossed = isCrossedOff(ing)
  const label =
    ing.amount !== null
      ? `${ing.name}: ${ing.amount}${ing.unit ? ` ${ing.unit}` : ''}`
      : ing.name
  return (
    <li key={ing.key}>
      <button
        type="button"
        aria-pressed={isCrossed}
        onClick={() =>
          setCrossed((prev) => {
            const next = new Map(prev)
            if (next.get(ing.key) === ing.amount) next.delete(ing.key)
            else next.set(ing.key, ing.amount)
            return next
          })
        }
        className="flex min-h-11 w-full items-center gap-3 rounded-xl border p-3 text-left"
        style={{ borderColor: 'var(--border)' }}
      >
        <span
          aria-hidden="true"
          className="flex h-5 w-5 shrink-0 items-center justify-center rounded"
          style={{
            border: `1.5px solid ${isCrossed ? 'var(--c-pos)' : 'var(--border-default)'}`,
            backgroundColor: isCrossed ? 'var(--c-pos)' : 'transparent',
            color: '#fff',
          }}
        >
          {isCrossed && <CheckIcon className="h-3.5 w-3.5" />}
        </span>
        <span
          className={isCrossed ? 'line-through' : undefined}
          style={{ color: isCrossed ? 'var(--text-subtle)' : undefined }}
        >
          {label}
        </span>
      </button>
    </li>
  )
})}
```

Add the icon import at the top of the file:

```jsx
import { CheckIcon } from '@heroicons/react/24/outline'
```

- [ ] **Step 5: Run to verify they pass**

Run: `npm run test -- ShoppingListPage`
Expected: PASS, including the pre-existing `ingredient amounts are scaled…` tests, whose `getByText` calls still find the untouched label span.

- [ ] **Step 6: Commit**

```bash
git add src/pages/ShoppingListPage.jsx src/pages/__tests__/ShoppingListPage.test.jsx
git commit -m "Make shopping list rows real tick boxes, invalidated by quantity

The rows were <li onClick> with a line-through: no button semantics, no
keyboard access, and nothing on screen saying they could be tapped. The
crossed set becomes a key -> amount-at-tick map, so changing a head-count
unticks exactly the rows whose quantity moved, with no effect and no
invalidation pass -- it is a comparison at render time."
```

---

## Task 14: Shopping list empty state

**Files:**
- Modify: `src/pages/ShoppingListPage.jsx`
- Test: `src/pages/__tests__/ShoppingListPage.test.jsx`

- [ ] **Step 1: Write the failing test**

```jsx
test('says so when the range holds no meals', async () => {
  mealPlansApi.fetchRange.mockResolvedValue({})

  render(<ShoppingListPage />)

  expect(
    await screen.findByText('No meals planned in this range.'),
  ).toBeInTheDocument()
})
```

- [ ] **Step 2: Run to verify it fails**

Run: `npm run test -- ShoppingListPage`
Expected: FAIL — text not found.

- [ ] **Step 3: Implement**

Inside the Recipes card, replace the bare `<ul>` with a guarded pair:

```jsx
{occurrences.length === 0 ? (
  <p
    className="py-6 text-center text-sm"
    style={{ color: 'var(--text-subtle)' }}
  >
    No meals planned in this range.
  </p>
) : (
  <ul className="space-y-2">
    {/* unchanged */}
  </ul>
)}
```

And the same shape in the Ingredients card:

```jsx
{ingredients.length === 0 ? (
  <p
    className="py-6 text-center text-sm"
    style={{ color: 'var(--text-subtle)' }}
  >
    Nothing to buy for this range yet.
  </p>
) : (
  <ul className="space-y-2">
    {/* unchanged */}
  </ul>
)}
```

- [ ] **Step 4: Run to verify it passes**

Run: `npm run test -- ShoppingListPage`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/pages/ShoppingListPage.jsx src/pages/__tests__/ShoppingListPage.test.jsx
git commit -m "Explain an empty shopping list instead of showing two blank cards"
```

---

## Task 15: Full verification

- [ ] **Step 1: Run the whole suite**

Run: `npm run test`
Expected: PASS. The count should exceed the 569 this branch started with by roughly the number of tests added above.

- [ ] **Step 2: Lint**

Run: `npm run lint`
Expected: clean, no output.

- [ ] **Step 3: Build**

Run: `npm run build`
Expected: succeeds.

- [ ] **Step 4: Manual pass**

Start the dev server (`npm run dev`, port 3000, bound to 0.0.0.0 so a phone on the same network can reach it). The backend must be running separately for real data: `uvicorn main:app --reload` from `backend/`, with `DATABASE_URL` set.

At **320 / 375 / 768 / 1280px**, confirm **no horizontal page scroll at any width**:

1. **Recipes** — the header holds only search and filter below md; the FAB reaches both creation paths; the filter sheet opens, filters, and dismisses by backdrop, Escape and its footer button; the funnel badge and the active-filter chips agree with what the grid shows; the card meta is one line at 320px; Delete asks before deleting; the FAB does not cover the last card row, including when the grid is filtered down to a single row.
2. **Shopping list** — one month below md and three above; the tabs switch and Ingredients is first; ticking works by touch and by keyboard; changing a head-count unticks the affected row and leaves the others; a long recipe title keeps its `×2` inline.
3. **Desktop regression** — the Recipes header, the `DateRangePicker`, the three-month calendar and the two-column shopping layout look identical to `main`.
4. **Keyboard only** — reach the FAB, the sheet, every chip, and both modals by accessible name.
5. **Other pages at 375px** — Ingredients and Import/Export, checking for fallout from the shared component changes.

Carried over from the previous branch and still unverified: **focus an `Input` on a real iOS device or Simulator and confirm the page does not zoom.** That fix shipped in `c4be323` and has never been seen working on hardware. Do not report it as working until someone has.

- [ ] **Step 5: Report what actually breaks**

Write down anything the manual pass turns up, with the width it happens at, before changing code.

---

## Task 16: Simplify

Required by `CLAUDE.md`: every plan ends with a simplification pass.

- [ ] **Step 1: Run the skill**

Invoke `/simplify`.

Points worth its attention, none of them decided in advance:

- `RecipesPage.jsx` has grown; the header and the filter surfaces may want to be their own components.
- `ConfirmModal` and `BottomSheet` both hand-roll the same Escape effect — and so does `DateRangePicker`. A `useDismissable(active, onDismiss)` hook may be worth extracting once there are three call sites.
- `ActiveFilterChips` and `RecipeFilters` both render a chip; they may share one.
- The `isCrossedOff` / batch-label logic may belong in `utils/shoppingList.js` beside `buildShoppingList`.
- `IngredientsPage` and `tutorial/tourStorage.js` still hand-roll guarded localStorage instead of `usePersistedState`, and `App.jsx:99` still hand-rolls a 44px box instead of `IconButton` — all three predate this diff. In scope for simplify only if it can be done without widening the branch.

- [ ] **Step 2: Re-verify after the pass**

Run: `npm run test && npm run lint && npm run build`
Expected: all PASS.

- [ ] **Step 3: Commit whatever the pass changed**

---

## Notes for whoever executes this

- **Do not push and do not open a PR** unless the user asks. `main` is untouched and so is the Railway deployment; keep it that way.
- Commit messages: this repo writes prose explaining *why*, not conventional-commit prefixes. Match the surrounding style, and end with the `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>` trailer.
- The Bash tool here is Git Bash, not PowerShell. PowerShell here-strings (`@'...'@`) silently mangle commit messages — use a heredoc.
- Every task's tests must fail before its implementation is written. If a test passes on the first run, it is testing the wrong thing.
