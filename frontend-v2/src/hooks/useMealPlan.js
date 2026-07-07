import React from 'react'
import { mealPlansApi } from '../api/mealPlansApi'
import { feedbackApi } from '../api/feedbackApi'
import { recipesApi } from '../api/recipesApi'

export const startOfWeek = (base) => {
  const start = new Date(base)
  const day = start.getDay()
  const diff = day === 0 ? -6 : 1 - day
  start.setDate(start.getDate() + diff)
  return start
}

export const fmt = (d) => d.toISOString().split('T')[0]

// Persist a single day's meals, forcing an overwrite if the day already exists.
const persistDay = async (date, dayMeals) => {
  const recipes = await recipesApi.fetchAll()
  const titleToId = Object.fromEntries(recipes.map((r) => [r.title, r.id]))
  const serialised = dayMeals.map((m) => ({
    main_id: titleToId[m.recipe],
    side_ids: (m.side_recipes || []).map((s) => titleToId[s]).filter(Boolean),
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
}

/**
 * Owns the calendar week view state and the persisted plan, plus the
 * main-meal actions (accept / reject / swap). Meal actions take an explicit
 * `cell` ({ date, mealIndex }) so the page can drive them from `activeCell`.
 */
export function useMealPlan({ setError }) {
  const today = React.useMemo(() => new Date(), [])
  const [viewStart, setViewStart] = React.useState(() => startOfWeek(today))
  const [plan, setPlan] = React.useState({})

  const weekDays = React.useMemo(
    () =>
      Array.from({ length: 7 }, (_, i) => {
        const d = new Date(viewStart)
        d.setDate(viewStart.getDate() + i)
        return d
      }),
    [viewStart]
  )

  const isToday = (d) => d.toDateString() === today.toDateString()

  React.useEffect(() => {
    async function load() {
      try {
        const viewEnd = new Date(viewStart)
        viewEnd.setDate(viewEnd.getDate() + 6)
        const data = await mealPlansApi.fetchRange(fmt(viewStart), fmt(viewEnd))
        setPlan(data || {})
      } catch (err) {
        console.error('Failed to load meal plan', err)
      }
    }
    load()
  }, [viewStart])

  const changeWeek = (delta) => {
    setViewStart((s) => {
      const d = new Date(s)
      d.setDate(d.getDate() + delta * 7)
      return d
    })
  }

  const handleAccept = async (cell) => {
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
    }
  }

  const handleReject = async (cell) => {
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
        i === mealIndex
          ? { ...m, recipe: replacement, accepted: false, leftover: false }
          : m
      )
      setPlan((p) => ({ ...p, [date]: updatedDay }))

      try {
        await persistDay(date, updatedDay)
      } catch (apiErr) {
        console.error('Failed to persist rejected meal', apiErr)
      }
    } catch (err) {
      console.error('Failed to reject meal', err)
    }
  }

  const handleSwap = async (cell, newTitle) => {
    if (!cell) return
    const { date, mealIndex } = cell
    const meal = plan[date]?.[mealIndex]
    if (!meal) return
    try {
      await feedbackApi.rejectRecipe(meal.recipe, date)
      await feedbackApi.acceptRecipe(newTitle, date)
      const updatedDay = plan[date].map((m, i) =>
        i === mealIndex
          ? { ...m, recipe: newTitle, accepted: false, leftover: false }
          : m
      )
      setPlan((p) => ({ ...p, [date]: updatedDay }))
      try {
        await persistDay(date, updatedDay)
      } catch (apiErr) {
        console.error('Failed to persist swapped meal', apiErr)
      }
    } catch (err) {
      console.error('Failed to swap meal', err)
    }
  }

  return {
    today,
    viewStart,
    weekDays,
    isToday,
    fmt,
    plan,
    setPlan,
    changeWeek,
    handleAccept,
    handleReject,
    handleSwap,
  }
}
