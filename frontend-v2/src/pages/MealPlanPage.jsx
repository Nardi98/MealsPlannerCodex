import React from 'react'
import {
  Card,
  Button,
  Input,
  TagSelector,
  MealActionModal,
} from '../components'
import OverwriteConfirmModal from '../components/OverwriteConfirmModal'
import { mealPlansApi } from '../api/mealPlansApi'
import { tagsApi } from '../api/tagsApi'
import { feedbackApi } from '../api/feedbackApi'
import { recipesApi } from '../api/recipesApi'
import { sideDishesApi } from '../api/sideDishesApi'
import { CheckIcon, XMarkIcon } from '@heroicons/react/24/outline'

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
  const [activeCell, setActiveCell] = React.useState(null)

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
  const [showOverwriteModal, setShowOverwriteModal] = React.useState(false)
  const [pendingGeneration, setPendingGeneration] = React.useState(null)

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target
    let val = type === 'checkbox' ? checked : value
    if (name === 'meals_per_day') {
      const num = Number(value)
      val = isNaN(num) ? 1 : Math.max(1, num)
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

  const executeGeneration = async ({ params, startDate, endDate, force = false }) => {
    const generated = await mealPlansApi.generate(params)
    const payload = {
      plan_date: startDate,
      plan: Object.fromEntries(
        Object.entries(generated || {}).map(([day, meals]) => [
          day,
          meals.map((m) => ({
            main_id: m.id,
            side_ids: [],
            leftover: m.leftover,
          })),
        ])
      ),
      bulk_leftovers: params.bulk_leftovers,
      keep_days: params.keep_days,
    }
    await mealPlansApi.create(payload, { force })
    const updated = await mealPlansApi.fetchRange(startDate, endDate)
    const resetAccepted = Object.fromEntries(
      Object.entries(updated || {}).map(([day, meals]) => [
        day,
        meals.map((m) => ({ ...m, accepted: false })),
      ])
    )
    setPlan(resetAccepted)
    setStart(new Date(startDate))
    setMessage('Plan generated successfully.')
  }

  const handleGenerate = async (e) => {
    e.preventDefault()
    setError('')
    setMessage('')
    const startDate = form.start
    const endDate = form.end
    const params = {
      start: form.start,
      days: Number(form.days),
      meals_per_day: Number(form.meals_per_day) || 1,
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
    try {
      const conflicts = await mealPlansApi.checkRange(startDate, endDate)
      if (conflicts && conflicts.length > 0) {
        setPendingGeneration({ params, startDate, endDate })
        setShowOverwriteModal(true)
        return
      }
      await executeGeneration({ params, startDate, endDate })
    } catch (err) {
      setError(err.message)
    }
  }

  const confirmOverwrite = async () => {
    if (!pendingGeneration) return
    setShowOverwriteModal(false)
    setError('')
    setMessage('')
    try {
      const { params, startDate, endDate } = pendingGeneration
      await mealPlansApi.deleteRange(startDate, endDate)
      await executeGeneration({ params, startDate, endDate, force: true })
    } catch (err) {
      setError(err.message)
    } finally {
      setPendingGeneration(null)
    }
  }

  const cancelOverwrite = () => {
    setShowOverwriteModal(false)
    setPendingGeneration(null)
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

  const handleAccept = async (cell = activeCell) => {
    if (!cell) return
    const { date, mealIndex } = cell
    const meal = plan[date]?.[mealIndex]
    if (!meal) return
    const { recipe: mainTitle, side_recipes: sides = [] } = meal
    try {
      await mealPlansApi.accept(date, mealIndex + 1, true)
      await Promise.all([
        feedbackApi.acceptRecipe(mainTitle, date),
        ...sides.map((s) => feedbackApi.acceptRecipe(s, date)),
      ])
      setPlan((p) => ({
        ...p,
        [date]: p[date].map((m, i) =>
          i === mealIndex ? { ...m, accepted: true } : m
        ),
      }))
    } catch (err) {
      console.error('Failed to accept meal', err)
    } finally {
      setActiveCell(null)
    }
  }

  const handleReject = async (cell = activeCell) => {
    if (!cell) return
    const { date, mealIndex } = cell
    const meal = plan[date]?.[mealIndex]
    if (!meal) return
    try {
      let replacement
      let attempts = 0
      do {
        replacement = await feedbackApi.rejectRecipe(meal.recipe, date)
        attempts += 1
      } while (
        replacement &&
        (replacement === meal.recipe || meal.side_recipes?.includes(replacement)) &&
        attempts < 5
      )
      if (
        !replacement ||
        replacement === meal.recipe ||
        meal.side_recipes?.includes(replacement)
      ) {
        setError('No replacement recipe available.')
        return
      }

      const updatedDay = plan[date].map((m, i) =>
        i === mealIndex ? { ...m, recipe: replacement, accepted: false } : m
      )
      setPlan((p) => ({ ...p, [date]: updatedDay }))

      try {
        const recipes = await recipesApi.fetchAll()
        const titleToId = Object.fromEntries(
          recipes.map((r) => [r.title, r.id])
        )
        const serialised = updatedDay.map((m) => ({
          main_id: titleToId[m.recipe],
          side_ids: (m.side_recipes || [])
            .map((s) => titleToId[s])
            .filter(Boolean),
          leftover: m.leftover,
        }))
        const payload = { plan_date: date, plan: { [date]: serialised } }
        try {
          await mealPlansApi.create(payload)
        } catch (apiErr) {
          if (apiErr.data?.conflicts) {
            await mealPlansApi.create(payload, { force: true })
          } else {
            throw apiErr
          }
        }
      } catch (apiErr) {
        console.error('Failed to persist rejected meal', apiErr)
      }
    } catch (err) {
      console.error('Failed to reject meal', err)
    }
  }

  const handleSwap = async (newTitle) => {
    if (!activeCell) return
    const { date, mealIndex } = activeCell
    const meal = plan[date]?.[mealIndex]
    if (!meal) return
    try {
      await feedbackApi.rejectRecipe(meal.recipe, date)
      await feedbackApi.acceptRecipe(newTitle, date)
      const updatedDay = plan[date].map((m, i) =>
        i === mealIndex ? { ...m, recipe: newTitle, accepted: false } : m
      )
      setPlan((p) => ({ ...p, [date]: updatedDay }))
      try {
        const recipes = await recipesApi.fetchAll()
        const titleToId = Object.fromEntries(
          recipes.map((r) => [r.title, r.id])
        )
        const serialised = updatedDay.map((m) => ({
          main_id: titleToId[m.recipe],
          side_ids: (m.side_recipes || [])
            .map((s) => titleToId[s])
            .filter(Boolean),
          leftover: m.leftover,
        }))
        const payload = { plan_date: date, plan: { [date]: serialised } }
        try {
          await mealPlansApi.create(payload)
        } catch (apiErr) {
          if (apiErr.data?.conflicts) {
            await mealPlansApi.create(payload, { force: true })
          } else {
            throw apiErr
          }
        }
      } catch (apiErr) {
        console.error('Failed to persist swapped meal', apiErr)
      }
    } catch (err) {
      console.error('Failed to swap meal', err)
    }
  }

  const handleAddSide = async () => {
    if (!activeCell) return
    const { date, mealIndex } = activeCell
    const meal = plan[date]?.[mealIndex]
    if (!meal) return
    try {
      const existing = meal.side_recipes || []
      const avoid = [meal.recipe, ...existing]
      const generated = await sideDishesApi.generate({
        avoid_titles: avoid,
      })
      if (!generated) {
        setError('No unique side dish available.')
        return
      }
      const { id, title } = generated
      await mealPlansApi.addSide(date, mealIndex + 1, id, meal.leftover)
      setPlan((p) => ({
        ...p,
        [date]: p[date].map((m, i) =>
          i === mealIndex
            ? { ...m, side_recipes: [...(m.side_recipes || []), title] }
            : m
        ),
      }))
    } catch (err) {
      console.error('Failed to add side dish', err)
      setError('No unique side dish available.')
    }
  }

  const handleRejectSide = async (sideIndex) => {
    if (!activeCell) return
    const { date, mealIndex } = activeCell
    const meal = plan[date]?.[mealIndex]
    const current = meal?.side_recipes?.[sideIndex]
    if (!meal || !current) return
    const existing = meal.side_recipes.filter((_, idx) => idx !== sideIndex)
    try {
      await feedbackApi.rejectRecipe(current, date)
      const avoid = [meal.recipe, ...existing]
      const replacement = await sideDishesApi.generate({
        avoid_titles: avoid,
      })
      if (!replacement) {
        setError('No replacement recipe available.')
        return
      }
      await mealPlansApi.replaceSide(
        date,
        mealIndex + 1,
        sideIndex,
        replacement.id,
        meal.leftover,
      )
      setPlan((p) => ({
        ...p,
        [date]: p[date].map((m, i) =>
          i === mealIndex
            ? {
                ...m,
                side_recipes: m.side_recipes.map((s, idx) =>
                  idx === sideIndex ? replacement.title : s
                ),
              }
            : m
        ),
      }))
    } catch (err) {
      console.error('Failed to reject side dish', err)
      setError('No replacement recipe available.')
    }
  }

  const handleRemoveSide = async (sideIndex) => {
    if (!activeCell) return
    const { date, mealIndex } = activeCell
    const meal = plan[date]?.[mealIndex]
    if (!meal) return
    try {
      await mealPlansApi.removeSide(date, mealIndex + 1, sideIndex, meal.leftover)
      setPlan((p) => ({
        ...p,
        [date]: p[date].map((m, i) =>
          i === mealIndex
            ? {
                ...m,
                side_recipes: m.side_recipes.filter((_, idx) => idx !== sideIndex),
              }
            : m
        ),
      }))
    } catch (err) {
      console.error('Failed to remove side dish', err)
    }
  }

  const handleSwapSide = async (sideIndex, newTitle) => {
    if (!activeCell) return
    const { date, mealIndex } = activeCell
    const meal = plan[date]?.[mealIndex]
    const oldTitle = meal?.side_recipes?.[sideIndex]
    if (!meal || !oldTitle) return
    const existing = meal.side_recipes.filter((_, idx) => idx !== sideIndex)
    if (newTitle === meal.recipe || existing.includes(newTitle)) {
      setError('Side dish already present.')
      return
    }
    try {
      await feedbackApi.rejectRecipe(oldTitle, date)
      await feedbackApi.acceptRecipe(newTitle, date)
      const recipes = await recipesApi.fetchAll()
      const titleToId = Object.fromEntries(recipes.map((r) => [r.title, r.id]))
      const newId = titleToId[newTitle]
      if (!newId) {
        setError('Replacement recipe not found.')
        return
      }
      await mealPlansApi.replaceSide(
        date,
        mealIndex + 1,
        sideIndex,
        newId,
        meal.leftover,
      )
      setPlan((p) => ({
        ...p,
        [date]: p[date].map((m, i) =>
          i === mealIndex
            ? {
                ...m,
                side_recipes: m.side_recipes.map((s, idx) =>
                  idx === sideIndex ? newTitle : s
                ),
              }
            : m
        ),
      }))
    } catch (err) {
      console.error('Failed to swap side dish', err)
    }
  }

  const activeMeal = activeCell
    ? plan[activeCell.date]?.[activeCell.mealIndex]
    : null
  const activeMealType = activeCell?.mealIndex === 1 ? 'dinner' : 'lunch'

  const renderCell = (d, idx) => {
    const iso = fmt(d)
    const meal = plan[iso]?.[idx]
    const acceptedStyle = meal?.accepted
      ? {
          backgroundColor: 'rgba(12, 58, 45, 0.15)',
          color: 'var(--text-strong)',
        }
      : {}
    return (
      <div
        key={`${idx}-${iso}`}
        className="relative border p-2 h-24 cursor-pointer"
        onClick={() => setActiveCell({ date: iso, mealIndex: idx })}
        style={
          isToday(d)
            ? {
                borderColor: 'var(--border)',
                color: 'var(--text-strong)',
                ...(meal?.accepted
                  ? acceptedStyle
                  : { backgroundColor: 'rgba(187, 138, 82, 0.15)' }),
              }
            : { borderColor: 'var(--border)', ...acceptedStyle }
        }
      >
        {meal ? (
          <>
            <div className="text-sm font-medium">
              {meal.recipe}
              {meal.leftover && (
                <img
                  src="/assets/icons/left_overs_icon.png"
                  alt="Leftover"
                  className="inline ml-1 h-4 w-4"
                />
              )}
            </div>
            {meal.side_recipes && meal.side_recipes.length > 0 && (
              <div className="mt-1 text-xs">
                {meal.side_recipes.join(', ')}
              </div>
            )}
            {!meal.accepted && (
              <div className="absolute bottom-1 right-1 flex space-x-1">
                <XMarkIcon
                  className="h-4 w-4 text-[color:var(--c-neg)] cursor-pointer"
                  onClick={(e) => {
                    e.stopPropagation()
                    handleReject({ date: iso, mealIndex: idx })
                  }}
                />
                <CheckIcon
                  className="h-4 w-4 text-[color:var(--c-pos)] cursor-pointer"
                  onClick={(e) => {
                    e.stopPropagation()
                    handleAccept({ date: iso, mealIndex: idx })
                  }}
                />
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
                    ? { backgroundColor: 'var(--c-a3)' }
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
      {activeCell && (
        <MealActionModal
          date={activeCell.date}
          meal={activeMealType}
          recipe={activeMeal?.recipe}
          sides={activeMeal?.side_recipes || []}
          accepted={activeMeal?.accepted}
          onAccept={handleAccept}
          onReject={handleReject}
          onSwap={handleSwap}
          onAddSide={handleAddSide}
          onRejectSide={handleRejectSide}
          onRemoveSide={handleRemoveSide}
          onSwapSide={handleSwapSide}
          onClose={() => setActiveCell(null)}
        />
      )}
      {showOverwriteModal && (
        <OverwriteConfirmModal
          onCancel={cancelOverwrite}
          onConfirm={confirmOverwrite}
        />
      )}
    </div>
  )
}

