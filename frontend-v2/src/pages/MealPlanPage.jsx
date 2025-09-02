import React from 'react'
import { Card } from '../components'

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
          {days.map((d) => (
            <div
              key={`lunch-${d.toISOString()}`}
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
            />
          ))}
          <div className="p-2 text-left font-medium">Dinner</div>
          {days.map((d) => (
            <div
              key={`dinner-${d.toISOString()}`}
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
            />
          ))}
        </div>
      </Card>
    </div>
  )
}

