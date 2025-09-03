import React from 'react'
import { Card, Input, Button } from '../components'

export default function ShoppingListPage() {
  const [startDate, setStartDate] = React.useState(
    () => new Date().toISOString().slice(0, 10),
  )
  const [endDate, setEndDate] = React.useState('')
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
          <Button variant="a1" onClick={() => setRecipes([])}>
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
                      {highlight && (
                        <div className="mt-0.5 h-1.5 w-1.5 rounded-full bg-[color:var(--c-a1)]" />
                      )}
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
      <Card>
        {ingredients.map((ing) => (
          <div key={ing.id}>{ing.name}</div>
        ))}
      </Card>
    </div>
  )
}

