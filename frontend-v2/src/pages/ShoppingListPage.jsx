import React from 'react'
import { Card, Input, Button } from '../components'
import { mealPlansApi } from '../api/mealPlansApi'
import { recipesApi } from '../api/recipesApi'

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
  const [ingredients, setIngredients] = React.useState([])

  React.useEffect(() => {
    const all = recipes
      .flatMap((r) => r.ingredients || [])
      .map((ing) => ({ id: ing.id, name: ing.name, done: false }))
    setIngredients(all)
  }, [recipes])

  const months = React.useMemo(() => {
    if (!startDate) return []
    const start = new Date(startDate)
    return Array.from({ length: 3 }, (_, i) => {
      const firstDay = new Date(start.getFullYear(), start.getMonth() + i, 1)
      const days = new Date(
        firstDay.getFullYear(),
        firstDay.getMonth() + 1,
        0,
      ).getDate()
      return { firstDay, days }
    })
  }, [startDate])

  const start = startDate ? new Date(startDate) : null
  const end = endDate ? new Date(endDate) : null

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
          <Input
            type="date"
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
          />
          <Input
            type="date"
            value={endDate}
            onChange={(e) => setEndDate(e.target.value)}
          />
          <Button variant="a1" onClick={handleLoad}>
            Load
          </Button>
        </div>
        <div className="flex justify-between px-8 text-xs">
          {months.map((m) => (
            <div
              key={m.firstDay.toISOString()}
              className="flex basis-[30%] flex-col items-center"
            >
              <div className="grid w-full grid-cols-7 gap-x-1 gap-y-2">
                {Array.from({ length: m.days }, (_, idx) => {
                  const day = idx + 1
                  const current = new Date(
                    m.firstDay.getFullYear(),
                    m.firstDay.getMonth(),
                    day,
                  )
                  const highlight =
                    start && end && current >= start && current <= end
                  return (
                    <div key={day} className="flex flex-col items-center">
                      {day}
                      <div
                        className={`mt-0.5 h-1.5 w-3 rounded-full ${
                          highlight
                            ? 'bg-[color:var(--c-a1)]'
                            : 'bg-white border border-[color:var(--border)] opacity-40'
                        }`}
                      />
                    </div>
                  )
                })}
              </div>
              <div className="mt-1 text-center">
                {m.firstDay.toLocaleString('default', { month: 'long' })}
              </div>
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
              <li key={r.id}>{r.title}</li>
            ))}
          </ul>
        </Card>
        <Card className="p-4 space-y-2">
          <h2
            className="text-lg font-medium"
            style={{ color: 'var(--text-strong)' }}
          >
            Ingredients
          </h2>
          <ul className="space-y-2">
            {ingredients.map((ing) => (
              <li key={ing.id}>
                <button
                  type="button"
                  onClick={() =>
                    setIngredients((prev) =>
                      prev.map((i) =>
                        i.id === ing.id ? { ...i, done: !i.done } : i,
                      ),
                    )
                  }
                  className={`text-left w-full cursor-pointer ${
                    ing.done ? 'line-through' : ''
                  }`}
                >
                  {ing.name}
                </button>
              </li>
            ))}
          </ul>
        </Card>
      </div>
    </div>
  )
}

