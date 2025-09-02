import React from 'react'
import { Card, Button, Input, TagSelector } from '../components'
import { mealPlansApi } from '../api/mealPlansApi'
import { tagsApi } from '../api/tagsApi'

export default function MealPlanPage() {
  const today = new Date()

  const startOfWeek = (base) => {
    const start = new Date(base)
    const day = start.getDay()
    const diff = day === 0 ? -6 : 1 - day
    start.setDate(start.getDate() + diff)
    return start
  }

  const [start, setStart] = React.useState(() => startOfWeek(today))

  const days = React.useMemo(
    () =>
      Array.from({ length: 7 }, (_, i) => {
        const d = new Date(start)
        d.setDate(start.getDate() + i)
        return d
      }),
    [start]
  )

  const isToday = (d) => d.toDateString() === today.toDateString()

  const fmt = (d) => d.toISOString().split('T')[0]
  const startIso = fmt(start)
  const end = new Date(start)
  end.setDate(start.getDate() + 6)
  const endIso = fmt(end)

  const [tags, setTags] = React.useState([])
  const [plan, setPlan] = React.useState({})

  const [form, setForm] = React.useState({
    start: startIso,
    end: endIso,
    days: 7,
    meals_per_day: 2,
    epsilon: 0,
    seasonality_weight: 1,
    recency_weight: 1,
    tag_penalty_weight: 1,
    bulk_bonus_weight: 1,
    keep_days: 3,
    bulk_leftovers: true,
    avoid_tags: [],
    reduce_tags: [],
  })
  const [message, setMessage] = React.useState('')
  const [error, setError] = React.useState('')

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target
    let val = type === 'checkbox' ? checked : value
    if (name === 'meals_per_day') {
      const num = Number(value)
      val = Math.min(2, Math.max(1, isNaN(num) ? 1 : num))
    }
    setForm((f) => ({ ...f, [name]: val }))
  }

  React.useEffect(() => {
    setForm((f) => ({ ...f, start: startIso, end: endIso }))
  }, [startIso, endIso])

  React.useEffect(() => {
    async function loadTags() {
      try {
        const data = await tagsApi.fetchAll()
        setTags(data.map((t) => t.name))
      } catch (err) {
        console.error('Failed to load tags', err)
      }
    }
    loadTags()
  }, [])

  const handleAvoidChange = (selected) =>
    setForm((f) => ({ ...f, avoid_tags: selected }))
  const handleReduceChange = (selected) =>
    setForm((f) => ({ ...f, reduce_tags: selected }))

  const handleGenerate = async (e) => {
    e.preventDefault()
    setError('')
    setMessage('')
    try {
      const params = {
        start: form.start,
        days: Number(form.days),
        meals_per_day: Math.min(2, Math.max(1, Number(form.meals_per_day))),
        epsilon: Number(form.epsilon),
        seasonality_weight: Number(form.seasonality_weight),
        recency_weight: Number(form.recency_weight),
        tag_penalty_weight: Number(form.tag_penalty_weight),
        bulk_bonus_weight: Number(form.bulk_bonus_weight),
        bulk_leftovers: Boolean(form.bulk_leftovers),
        avoid_tags: form.avoid_tags,
        reduce_tags: form.reduce_tags,
        keep_days: Number(form.keep_days),
      }
      const generated = await mealPlansApi.generate(params)
      const payload = {
        plan_date: form.start,
        plan: Object.fromEntries(
          Object.entries(generated).map(([day, meals]) => [
            day,
            meals.map((m) => ({ main_id: m.id, side_ids: [] })),
          ]),
        ),
        bulk_leftovers: Boolean(form.bulk_leftovers),
        keep_days: Number(form.keep_days),
      }
      try {
        await mealPlansApi.create(payload)
      } catch (err) {
        if (err.data?.conflicts) {
          const days = err.data.conflicts.join(', ')
          const overwrite = window.confirm(
            `Conflicts on: ${days}. Overwrite existing plans?`
          )
          if (overwrite) {
            await mealPlansApi.create(payload, { force: true })
          } else {
            setError(`Conflicts on: ${days}`)
            return
          }
        } else {
          throw err
        }
      }
      const updated = await mealPlansApi.fetchRange(form.start, form.end)
      setPlan(updated || {})
      setStart(new Date(form.start))
      setMessage('Plan generated successfully.')
    } catch (err) {
      setError(err.message)
    }
  }

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

  const changeWeek = (delta) => {
    setStart((s) => {
      const d = new Date(s)
      d.setDate(d.getDate() + delta)
      return d
    })
  }

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
      <div className="flex justify-between">
        <Button variant="ghost" onClick={() => changeWeek(-7)}>
          Previous week
        </Button>
        <Button variant="ghost" onClick={() => changeWeek(7)}>
          Next week
        </Button>
      </div>
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
      <Card>
        <form onSubmit={handleGenerate} className="space-y-4">
          <div className="grid grid-cols-2 gap-2">
            <label className="flex flex-col text-sm">
              <span className="mb-1">Start date</span>
              <Input type="date" name="start" value={form.start} onChange={handleChange} />
            </label>
            <label className="flex flex-col text-sm">
              <span className="mb-1">End date</span>
              <Input type="date" name="end" value={form.end} onChange={handleChange} />
            </label>
            <label className="flex flex-col text-sm">
              <span className="mb-1">Days</span>
              <Input type="number" name="days" min="1" value={form.days} onChange={handleChange} />
            </label>
            <label className="flex flex-col text-sm">
              <span className="mb-1">Meals per day</span>
              <Input
                type="number"
                name="meals_per_day"
                min="1"
                max="2"
                step="1"
                value={form.meals_per_day}
                onChange={handleChange}
              />
            </label>
            <label className="flex flex-col text-sm">
              <span className="mb-1">ε ({form.epsilon})</span>
              <Input
                type="range"
                name="epsilon"
                min="0"
                max="1"
                step="0.01"
                value={form.epsilon}
                onChange={handleChange}
              />
            </label>
            <label className="flex flex-col text-sm">
              <span className="mb-1">Seasonality weight</span>
              <Input type="number" step="0.1" name="seasonality_weight" value={form.seasonality_weight} onChange={handleChange} />
            </label>
            <label className="flex flex-col text-sm">
              <span className="mb-1">Recency weight</span>
              <Input type="number" step="0.1" name="recency_weight" value={form.recency_weight} onChange={handleChange} />
            </label>
            <label className="flex flex-col text-sm">
              <span className="mb-1">Tag penalty weight</span>
              <Input type="number" step="0.1" name="tag_penalty_weight" value={form.tag_penalty_weight} onChange={handleChange} />
            </label>
            <label className="flex flex-col text-sm">
              <span className="mb-1">Bulk bonus weight</span>
              <Input type="number" step="0.1" name="bulk_bonus_weight" value={form.bulk_bonus_weight} onChange={handleChange} />
            </label>
            <label className="flex flex-col text-sm">
              <span className="mb-1">Keep days</span>
              <Input type="number" name="keep_days" min="0" value={form.keep_days} onChange={handleChange} />
            </label>
            <label className="flex items-center gap-2 col-span-2 text-sm">
              <input
                type="checkbox"
                name="bulk_leftovers"
                checked={form.bulk_leftovers}
                onChange={handleChange}
                className="h-4 w-4 rounded border"
                style={{ borderColor: 'var(--border)' }}
              />
              <span style={{ color: 'var(--text-strong)' }}>Bulk leftovers</span>
            </label>
            <TagSelector
              label="Avoid tags"
              tags={tags}
              selected={form.avoid_tags}
              onChange={handleAvoidChange}
            />
            <TagSelector
              label="Reduce tags"
              tags={tags}
              selected={form.reduce_tags}
              onChange={handleReduceChange}
            />
          </div>
          {message && (
            <div className="text-sm" style={{ color: 'var(--c-pos)' }}>
              {message}
            </div>
          )}
          {error && (
            <div className="text-sm" style={{ color: 'var(--c-neg)' }}>
              {error}
            </div>
          )}
          <Button type="submit">Generate plan</Button>
        </form>
      </Card>
    </div>
  )
}

