import React from 'react'
import { Card, Input, Button, MonthGrid } from '../components'
import { mealPlansApi } from '../api/mealPlansApi'
import { recipesApi } from '../api/recipesApi'
import { buildShoppingList, formatExportText } from '../utils/shoppingList'

export default function ShoppingListPage() {
  const [startDate, setStartDate] = React.useState(() =>
    new Date().toISOString().slice(0, 10),
  )
  const [endDate, setEndDate] = React.useState(() => {
    const d = new Date()
    d.setDate(d.getDate() + ((7 - d.getDay()) % 7))
    return d.toISOString().slice(0, 10)
  })
  const [recipes, setRecipes] = React.useState([])

  const ingredients = React.useMemo(() => buildShoppingList(recipes), [recipes])

  const start = startDate ? new Date(startDate) : null
  const end = endDate ? new Date(endDate) : null

  const handleExport = () => {
    if (!start) return
    const items = ingredients.map(({ name }) => ({ label: name }))
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
    const start = new Date(startDate)
    const base = new Date(start.getFullYear(), start.getMonth(), 1)
    return Array.from({ length: 3 }, (_, i) => {
      const d = new Date(base)
      d.setMonth(base.getMonth() + i)
      return d
    })
  }, [startDate])

  const handleLoad = React.useCallback(async () => {
    try {
      const data = await mealPlansApi.fetchRange(startDate, endDate || startDate)
      const titles = new Set()
      Object.values(data || {}).forEach((meals) => {
        meals.forEach((m) => {
          titles.add(m.recipe.replace(' (leftover)', ''))
          for (const t of m.side_recipes || []) {
            titles.add(t)
          }
        })
      })
      const all = await recipesApi.fetchAll()
      setRecipes(all.filter((r) => titles.has(r.title)))
    } catch (err) {
      console.error('Failed to load shopping list', err)
    }
  }, [startDate, endDate])

  React.useEffect(() => {
    if (startDate && endDate) {
      handleLoad()
    }
  }, [startDate, endDate, handleLoad])

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
          <label className="flex flex-col text-sm">
            <span className="mb-1">Begin date</span>
            <Input
              type="date"
              value={startDate}
              onChange={(e) => {
                const value = e.target.value
                setStartDate(value)
                if (endDate && new Date(value) > new Date(endDate)) {
                  setEndDate(value)
                }
              }}
            />
          </label>
          <label className="flex flex-col text-sm">
            <span className="mb-1">End date</span>
            <Input
              type="date"
              value={endDate}
              onChange={(e) => {
                const value = e.target.value
                setEndDate(value)
                if (startDate && new Date(value) < new Date(startDate)) {
                  setStartDate(value)
                }
              }}
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
            className="pb-2 border-b"
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
            {recipes.map((r) => (
              <li
                key={r.id}
                className="border rounded-xl p-3"
                style={{ borderColor: 'var(--border)' }}
              >
                <div>{r.title}</div>
                <div className="text-xs text-[color:var(--text-subtle)]">
                  {(r.ingredients || []).length} ingredients
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
            <Button variant="a2" onClick={handleExport}>
              Export open items
            </Button>
          </div>
          <ul className="space-y-2">
            {ingredients.map((ing) => (
              <li
                key={ing.key}
                className="border rounded-xl p-3 flex items-center gap-2"
                style={{ borderColor: 'var(--border)' }}
              >
                <span
                  className="w-3 h-3 rounded-full border flex-shrink-0"
                  style={{ borderColor: 'var(--c-a1)' }}
                />
                <span>{ing.name}</span>
              </li>
            ))}
          </ul>
        </Card>
      </div>
    </div>
  )
}

