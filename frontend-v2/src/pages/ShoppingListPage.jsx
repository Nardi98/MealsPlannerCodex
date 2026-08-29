import React from 'react'
import { format } from 'date-fns'
import { CheckIcon } from '@heroicons/react/24/outline'
import {
  Card,
  Button,
  ViewToggle,
  Input,
  MonthGrid,
  DateRangePicker,
  MergeIngredientsModal,
} from '../components'
import { useIsMobile } from '../hooks/useIsMobile'
import { mealPlansApi } from '../api/mealPlansApi'
import { recipesApi } from '../api/recipesApi'
import { authApi } from '../api/authApi'
import {
  buildShoppingList,
  batchLabel,
  formatExportText,
} from '../utils/shoppingList'

// Meal slots are numbered 1/2; the shopping list reads them back as dayparts.
const MEAL_SLOT = { 1: 'Lunch', 2: 'Dinner' }

export default function ShoppingListPage() {
  const isMobile = useIsMobile()
  // Ingredients first: it is the half you hold up in a shop.
  const [tab, setTab] = React.useState('ingredients')
  const [startDate, setStartDate] = React.useState(() =>
    new Date().toISOString().slice(0, 10),
  )
  const [endDate, setEndDate] = React.useState(() => {
    const d = new Date()
    d.setDate(d.getDate() + ((7 - d.getDay()) % 7))
    return d.toISOString().slice(0, 10)
  })
  // Each occurrence is one planned meal (main + its sides) with the number of
  // people it is cooked for; the same recipe on two days yields two occurrences.
  const [occurrences, setOccurrences] = React.useState([])
  const [recipesByTitle, setRecipesByTitle] = React.useState(() => new Map())
  const [people, setPeople] = React.useState(2)
  // Ingredient key -> the amount that was on screen when it was ticked.
  //
  // Keying on the amount as well as the key is what makes a head-count change
  // untick the rows it actually affected: a row counts as ticked only while
  // the amount still matches, so the invalidation is a comparison at render
  // time rather than an effect that has to notice the change and go hunting
  // for stale entries.
  const [crossed, setCrossed] = React.useState(() => new Map())
  const [merging, setMerging] = React.useState(false)

  // One pass over the occurrences produces both halves of the page: the summed
  // ingredient list, and the per-recipe batch labels the Recipes card shows.
  // Every recipe is scaled from its own authored basis to the meal's people
  // count (sides scale with their parent meal, which is why they carry the same
  // head-count). A label is null when the meal cooks the recipe exactly as
  // written, which is the common case and shows nothing.
  const { ingredients, labelsByOccurrence } = React.useMemo(() => {
    const items = []
    const labels = new Map()

    occurrences.forEach((o) => {
      const main = recipesByTitle.get(o.mainTitle)
      if (main) {
        items.push({
          people: o.people,
          servings: main.servings,
          ingredients: main.ingredients,
        })
      }
      const sideLabels = o.sideTitles.map((title) => {
        const side = recipesByTitle.get(title)
        if (side) {
          items.push({
            people: o.people,
            servings: side.servings,
            ingredients: side.ingredients,
          })
        }
        return batchLabel(o.people, side?.servings)
      })
      labels.set(`${o.planDate}-${o.mealNumber}`, {
        main: batchLabel(o.people, main?.servings),
        sides: sideLabels,
      })
    })

    return {
      ingredients: buildShoppingList(items),
      labelsByOccurrence: labels,
    }
  }, [occurrences, recipesByTitle])

  const start = startDate ? new Date(startDate) : null
  const end = endDate ? new Date(endDate) : null

  // One definition, used by the list and by the export, so the two can never
  // disagree about what counts as ticked.
  const isCrossedOff = (ing) => crossed.get(ing.key) === ing.amount

  const handleExport = () => {
    if (!start) return
    const items = ingredients
      .filter((ing) => !isCrossedOff(ing))
      .map(({ name, amount, unit }) => ({ name, amount, unit }))
    const text = formatExportText(items, start, end || start)
    const blob = new Blob([text], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `shopping-list_${startDate}_${endDate || startDate}.txt`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

  // The grid is read-only: it only tints a range the picker directly above
  // already states in words. Three of them full-width is two screens before
  // any content on a phone, so one is confirmation enough there.
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

  const handleLoad = React.useCallback(async () => {
    try {
      const data = await mealPlansApi.fetchRange(startDate, endDate || startDate)
      const list = []
      Object.entries(data || {}).forEach(([day, meals]) => {
        // A day is indexed by meal_number, so an unfilled slot arrives as null.
        meals.filter(Boolean).forEach((m) => {
          list.push({
            planDate: day,
            mealNumber: m.meal_number,
            people: m.people,
            leftover: m.leftover,
            mainTitle: m.recipe,
            sideTitles: m.side_recipes || [],
          })
        })
      })
      list.sort(
        (a, b) =>
          a.planDate.localeCompare(b.planDate) || a.mealNumber - b.mealNumber,
      )
      setOccurrences(list)
      setCrossed(new Map())
    } catch (err) {
      console.error('Failed to load shopping list', err)
    }
  }, [startDate, endDate])

  // The recipe catalog is independent of the selected range, so fetch it once.
  React.useEffect(() => {
    recipesApi
      .fetchAll()
      .then((all) => setRecipesByTitle(new Map(all.map((r) => [r.title, r]))))
      .catch((err) => console.error('Failed to load recipes', err))
  }, [])

  // Seed the global People box from the user's saved default.
  React.useEffect(() => {
    authApi
      .me()
      .then((me) => {
        if (me?.default_people) setPeople(me.default_people)
      })
      .catch((err) => console.error('Failed to load user', err))
  }, [])

  React.useEffect(() => {
    if (startDate && endDate) {
      handleLoad()
    }
  }, [startDate, endDate, handleLoad])

  // Persist the global people count and overwrite every in-range meal. The
  // occurrences on screen are exactly that range, so update them in place
  // rather than refetching.
  const commitGlobalPeople = async (value) => {
    const next = Math.max(1, Math.round(value) || 1)
    setPeople(next)
    setOccurrences((prev) => prev.map((o) => ({ ...o, people: next })))
    try {
      await authApi.setDefaultPeople({
        people: next,
        startDate,
        endDate: endDate || startDate,
      })
    } catch (err) {
      console.error('Failed to set default people', err)
    }
  }

  // Adjust a single meal's people count and persist it.
  const changeMealPeople = async (occ, delta) => {
    const next = Math.max(1, occ.people + delta)
    if (next === occ.people) return
    setOccurrences((prev) =>
      prev.map((o) =>
        o.planDate === occ.planDate && o.mealNumber === occ.mealNumber
          ? { ...o, people: next }
          : o,
      ),
    )
    try {
      await mealPlansApi.setPeople(occ.planDate, occ.mealNumber, next)
    } catch (err) {
      console.error('Failed to set meal people', err)
    }
  }

  // Extracted so the mobile branch can show one at a time without the JSX
  // being written twice; the desktop branch renders the pair exactly as before.
  const recipesCard = (
    <Card className="p-4 space-y-2">
      <div
        className="pb-4 border-b"
        style={{ borderColor: 'var(--border)' }}
      >
        <h2
          className="text-lg font-medium"
          style={{ color: 'var(--text-strong)' }}
        >
          Recipes
        </h2>
      </div>
      {occurrences.length === 0 ? (
        <p className="py-6 text-center text-sm" style={{ color: 'var(--text-subtle)' }}>
          No meals planned in this range.
        </p>
      ) : (
      <ul className="space-y-2">
        {occurrences.map((o) => {
          const key = `${o.planDate}-${o.mealNumber}`
          const labels = labelsByOccurrence.get(key) || { sides: [] }
          return (
          <li
            key={key}
            className="border rounded-xl p-3 flex flex-wrap items-center justify-between gap-3"
            style={{ borderColor: 'var(--border)' }}
          >
            <div className="min-w-0">
              <div className="text-xs text-[color:var(--text-subtle)]">
                {format(new Date(o.planDate), 'EEE d MMM')} ·{' '}
                {MEAL_SLOT[o.mealNumber] || `Meal ${o.mealNumber}`}
                {o.leftover ? ' · leftover' : ''}
              </div>
              {/* Inline flow, not a flex row: as two flex items a long title
                  pushed the batch label onto its own unaligned line. */}
              <div>
                {o.mainTitle}
                {labels.main && (
                  <span className="ml-2 text-xs tabular-nums text-[color:var(--text-subtle)]">
                    {labels.main}
                  </span>
                )}
              </div>
              {o.sideTitles.length > 0 && (
                <div className="text-xs text-[color:var(--text-subtle)]">
                  +{' '}
                  {o.sideTitles.map((title, i) => (
                    <React.Fragment key={title}>
                      {i > 0 && ', '}
                      {title}
                      {labels.sides[i] && (
                        <span className="tabular-nums"> {labels.sides[i]}</span>
                      )}
                    </React.Fragment>
                  ))}
                </div>
              )}
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <Button
                variant="a2"
                onClick={() => changeMealPeople(o, -1)}
                aria-label="Fewer people"
              >
                –
              </Button>
              <span className="w-6 text-center tabular-nums">
                {o.people}
              </span>
              <Button
                variant="a2"
                onClick={() => changeMealPeople(o, 1)}
                aria-label="More people"
              >
                +
              </Button>
            </div>
          </li>
          )
        })}
      </ul>
      )}
    </Card>
  )

  const ingredientsCard = (
    <Card className="p-4 space-y-2">
      <div
        className="flex flex-wrap items-center justify-between gap-2 pb-2 border-b"
        style={{ borderColor: 'var(--border)' }}
      >
        <h2
          className="text-lg font-medium"
          style={{ color: 'var(--text-strong)' }}
        >
          Ingredients
        </h2>
        <div className="flex flex-wrap gap-2">
          <Button variant="a2" onClick={() => setMerging(true)}>
            Merge ingredients
          </Button>
          <Button variant="a2" onClick={handleExport}>
            Export open items
          </Button>
        </div>
      </div>
      {ingredients.length === 0 ? (
        <p className="py-6 text-center text-sm" style={{ color: 'var(--text-subtle)' }}>
          Nothing to buy for this range yet.
        </p>
      ) : (
      <ul className="space-y-2">
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
                    border: `1.5px solid ${
                      isCrossed ? 'var(--c-pos)' : 'var(--border-default)'
                    }`,
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
      </ul>
      )}
    </Card>
  )

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap justify-between items-end gap-3">
        <div>
          <h1
            className="text-2xl font-medium"
            style={{ color: 'var(--text-strong)' }}
          >
            Shopping List
          </h1>
          <p className="text-sm text-[color:var(--text-subtle)]">
            Select a date range to highlight days covered by this grocery list.
          </p>
        </div>
        <div className="flex flex-wrap items-end gap-2">
          <DateRangePicker
            label="Date range"
            align="right"
            start={startDate}
            end={endDate}
            onChange={({ start, end }) => {
              setStartDate(start)
              setEndDate(end)
            }}
          />
          <label className="block">
            <span className="mb-2 block font-bold text-base">People</span>
            <Input
              type="number"
              min={1}
              className="w-24"
              value={people}
              onChange={(e) => setPeople(e.target.value)}
              onBlur={(e) => commitGlobalPeople(Number(e.target.value))}
            />
          </label>
        </div>
      </div>
      <Card className="px-4 py-4 md:px-8 md:py-6">
        <div className="flex flex-wrap justify-between gap-4 text-xs">
          {months.map((m) => (
            <div
              key={m.toISOString()}
              data-testid="shopping-month"
              className="flex basis-full justify-center md:basis-[30%]"
            >
              <MonthGrid baseDate={m} startDate={start} endDate={end} />
            </div>
          ))}
        </div>
      </Card>
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
      {merging && (
        <MergeIngredientsModal
          onClose={() => setMerging(false)}
          onMerged={handleLoad}
        />
      )}
    </div>
  )
}
