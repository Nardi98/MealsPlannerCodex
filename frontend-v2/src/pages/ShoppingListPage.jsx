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
  const [crossed, setCrossed] = React.useState(() => new Set())

  const ingredients = React.useMemo(() => buildShoppingList(recipes), [recipes])

  const toggle = (key) => {
    setCrossed((prev) => {
      const next = new Set(prev)
      next.has(key) ? next.delete(key) : next.add(key)
      return next
    })
  }

  const start = startDate ? new Date(startDate) : null
  const end = endDate ? new Date(endDate) : null

  const handleExport = () => {
    if (!start) return
    const items = ingredients.map(({ key, name }) => ({ id: key, label: name }))
    const text = formatExportText(items, crossed, start, end || start)
    const blob = new Blob([text], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `shopping-list_${startDate}_${endDate || startDate}.txt`
    a.click()
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

  const handleLoad = async () => {
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
  }

  return (
    <div className="space-y-4">
      <h1
        className="text-xl font-medium"
        style={{ color: 'var(--text-strong)' }}
      >
        Shopping List
      </h1>
      <Card className="space-y-8">
        <div className="flex items-center gap-2 px-8">
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
          <Button variant="a1" onClick={handleLoad}>
            Load
          </Button>
        </div>
        <div className="flex justify-between px-8 text-xs">
          {months.map((m) => (
            <div key={m.toISOString()} className="flex basis-[30%] justify-center">
              <MonthGrid baseDate={m} startDate={start} endDate={end} />
            </div>
          ))}
        </div>
      </Card>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card className="p-4 space-y-2">
          <h2
            className="text-lg font-medium"
            style={{ color: 'var(--text-strong)' }}
          >
            Recipes
          </h2>
          <ul className="space-y-2">
            {recipes.map((r) => (
              <li key={r.id}>
                {r.title}
                <span className="ml-1 text-xs text-[color:var(--text-subtle)]">
                  {(r.ingredients || []).length}
                </span>
              </li>
            ))}
          </ul>
        </Card>
        <Card className="p-4 space-y-2">
          <div className="flex items-center justify-between">
            <h2
              className="text-lg font-medium"
              style={{ color: 'var(--text-strong)' }}
            >
              Ingredients
            </h2>
            <Button variant="a2" onClick={handleExport}>
              Export
            </Button>
          </div>
          <ul className="space-y-2">
            {ingredients.map((ing) => (
              <li key={ing.key}>
                <button
                  type="button"
                  onClick={() => toggle(ing.key)}
                  className="flex items-center gap-2 text-left w-full cursor-pointer"
                >
                  <span
                    className="w-3 h-3 border border-[color:var(--c-a1)] flex-shrink-0"
                    style={{
                      background: crossed.has(ing.key)
                        ? 'var(--c-a1)'
                        : 'transparent',
                    }}
                  />
                  <span className={crossed.has(ing.key) ? 'line-through' : ''}>
                    {ing.name}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </Card>
      </div>
    </div>
  )
}

