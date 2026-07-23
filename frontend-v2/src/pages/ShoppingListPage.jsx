import React from 'react'
import { format } from 'date-fns'
import {
  Card,
  Button,
  Input,
  MonthGrid,
  DateRangePicker,
  MergeIngredientsModal,
} from '../components'
import { mealPlansApi } from '../api/mealPlansApi'
import { recipesApi } from '../api/recipesApi'
import { authApi } from '../api/authApi'
import { buildShoppingList, formatExportText } from '../utils/shoppingList'

// Meal slots are numbered 1/2; the shopping list reads them back as dayparts.
const MEAL_SLOT = { 1: 'Lunch', 2: 'Dinner' }

export default function ShoppingListPage() {
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
  const [crossed, setCrossed] = React.useState(new Set())
  const [merging, setMerging] = React.useState(false)

  // Each occurrence contributes its main and every side, all scaled by the
  // meal's own people count (sides scale with their parent meal).
  const ingredients = React.useMemo(() => {
    const items = []
    occurrences.forEach((o) => {
      const main = recipesByTitle.get(o.mainTitle)
      if (main) items.push({ people: o.people, ingredients: main.ingredients })
      o.sideTitles.forEach((title) => {
        const side = recipesByTitle.get(title)
        if (side) items.push({ people: o.people, ingredients: side.ingredients })
      })
    })
    return buildShoppingList(items)
  }, [occurrences, recipesByTitle])

  const start = startDate ? new Date(startDate) : null
  const end = endDate ? new Date(endDate) : null

  const handleExport = () => {
    if (!start) return
    const items = ingredients
      .filter((ing) => !crossed.has(ing.key))
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

  const months = React.useMemo(() => {
    if (!startDate) return []
    const base = new Date(startDate)
    const first = new Date(base.getFullYear(), base.getMonth(), 1)
    return Array.from({ length: 3 }, (_, i) => {
      const d = new Date(first)
      d.setMonth(first.getMonth() + i)
      return d
    })
  }, [startDate])

  const handleLoad = React.useCallback(async () => {
    try {
      const data = await mealPlansApi.fetchRange(startDate, endDate || startDate)
      const list = []
      Object.entries(data || {}).forEach(([day, meals]) => {
        meals.forEach((m) => {
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
      setCrossed(new Set())
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

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-end">
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
        <div className="flex items-end gap-2">
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
      <Card className="px-8 py-6">
        <div className="flex justify-between text-xs">
          {months.map((m) => (
            <div key={m.toISOString()} className="flex basis-[30%] justify-center">
              <MonthGrid baseDate={m} startDate={start} endDate={end} />
            </div>
          ))}
        </div>
      </Card>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
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
          <ul className="space-y-2">
            {occurrences.map((o) => (
              <li
                key={`${o.planDate}-${o.mealNumber}`}
                className="border rounded-xl p-3 flex items-center justify-between gap-3"
                style={{ borderColor: 'var(--border)' }}
              >
                <div>
                  <div className="text-xs text-[color:var(--text-subtle)]">
                    {format(new Date(o.planDate), 'EEE d MMM')} ·{' '}
                    {MEAL_SLOT[o.mealNumber] || `Meal ${o.mealNumber}`}
                    {o.leftover ? ' · leftover' : ''}
                  </div>
                  <div>{o.mainTitle}</div>
                  {o.sideTitles.length > 0 && (
                    <div className="text-xs text-[color:var(--text-subtle)]">
                      + {o.sideTitles.join(', ')}
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
            ))}
          </ul>
        </Card>
        <Card className="p-4 space-y-2">
          <div
            className="flex items-center justify-between pb-2 border-b"
            style={{ borderColor: 'var(--border)' }}
          >
            <h2
              className="text-lg font-medium"
              style={{ color: 'var(--text-strong)' }}
            >
              Ingredients
            </h2>
            <div className="flex gap-2">
              <Button variant="a2" onClick={() => setMerging(true)}>
                Merge ingredients
              </Button>
              <Button variant="a2" onClick={handleExport}>
                Export open items
              </Button>
            </div>
          </div>
          <ul className="space-y-2">
            {ingredients.map((ing) => {
              const isCrossed = crossed.has(ing.key)
              const label =
                ing.amount !== null
                  ? `${ing.name}: ${ing.amount}${ing.unit ? ` ${ing.unit}` : ''}`
                  : ing.name
              return (
                <li
                  key={ing.key}
                  onClick={() =>
                    setCrossed((prev) => {
                      const next = new Set(prev)
                      if (next.has(ing.key)) next.delete(ing.key)
                      else next.add(ing.key)
                      return next
                    })
                  }
                  className={`border rounded-xl p-3 cursor-pointer${
                    isCrossed ? ' line-through text-[color:var(--text-subtle)]' : ''
                  }`}
                  style={{ borderColor: 'var(--border)' }}
                >
                  {label}
                </li>
              )
            })}
          </ul>
        </Card>
      </div>
      {merging && (
        <MergeIngredientsModal
          onClose={() => setMerging(false)}
          onMerged={handleLoad}
        />
      )}
    </div>
  )
}
