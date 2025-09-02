import React from 'react'
import { Card } from '../components'
import { mealPlansApi } from '../api/mealPlansApi'

export default function MealPlanPage() {
  const today = new Date()
  const start = new Date(today)
  const day = start.getDay()
  const diff = day === 0 ? -6 : 1 - day
  start.setDate(start.getDate() + diff)
  const days = Array.from({ length: 7 }, (_, i) => {
    const d = new Date(start)
    d.setDate(start.getDate() + i)
    return d
  })
  const isToday = (d) => d.toDateString() === today.toDateString()

  const fmt = (d) => d.toISOString().split('T')[0]
  const startIso = fmt(start)
  const end = new Date(start)
  end.setDate(start.getDate() + 6)
  const endIso = fmt(end)

  const [plan, setPlan] = React.useState({})

  React.useEffect(() => {
    async function load() {
      try {
        const data = await mealPlansApi.fetchRange(startIso, endIso)
        setPlan(data || {})
      } catch (err) {
        console.error('Failed to load meal plan', err)
      }
    }
    load()
  }, [startIso, endIso])

  const renderCell = (d, idx) => {
    const iso = fmt(d)
    const meal = plan[iso]?.[idx]
    return (
      <div
        key={`${idx}-${iso}`}
        className="border p-2 h-24"
        style={
          isToday(d)
            ? {
                borderColor: 'var(--border)',
                backgroundColor: 'var(--c-a1)',
                opacity: 0.1,
              }
            : { borderColor: 'var(--border)' }
        }
      >
        {meal ? (
          <>
            <div className="text-sm font-medium">{meal.recipe}</div>
            {meal.side_recipes && meal.side_recipes.length > 0 && (
              <div className="mt-1 text-xs">
                {meal.side_recipes.join(', ')}
              </div>
            )}
          </>
        ) : (
          <div className="text-sm text-[color:var(--text-subtle)]">—</div>
        )}
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-medium" style={{ color: 'var(--text-strong)' }}>
        Meal Plan
      </h1>
      <Card>
        <div className="grid grid-cols-8">
          <div />
          {days.map((d) => {
            const weekday = d.toLocaleDateString(undefined, { weekday: 'short' })
            const dm = `${d.getDate()}/${d.getMonth() + 1}`
            return (
              <div
                key={d.toISOString()}
                className={`p-2 text-center ${
                  isToday(d) ? 'text-white rounded-t-lg' : ''
                }`}
                style={
                  isToday(d)
                    ? { backgroundColor: 'var(--c-a1)' }
                    : undefined
                }
              >
                <div className="font-medium">{weekday}</div>
                <div className="text-sm">{dm}</div>
              </div>
            )
          })}
          <div className="p-2 text-left font-medium">Lunch</div>
          {days.map((d) => renderCell(d, 0))}
          <div className="p-2 text-left font-medium">Dinner</div>
          {days.map((d) => renderCell(d, 1))}
        </div>
      </Card>
    </div>
  )
}

