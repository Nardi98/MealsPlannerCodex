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

// Persist one or more days' meals in a single request, forcing an overwrite if
// any day already exists. `anchorDate` names the plan_date the response echoes.
const persistDays = async (anchorDate, daysMap) => {
  const recipes = await recipesApi.fetchAll()
  const titleToId = Object.fromEntries(recipes.map((r) => [r.title, r.id]))
  const serialise = (dayMeals) =>
    dayMeals.map((m) => ({
      main_id: titleToId[m.recipe],
      side_ids: (m.side_recipes || []).map((s) => titleToId[s]).filter(Boolean),
      leftover: m.leftover,
    }))
  const plan = Object.fromEntries(
    Object.entries(daysMap).map(([day, meals]) => [day, serialise(meals)])
  )
  const payload = { plan_date: anchorDate, plan }
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
  // The cell currently armed for a position swap (yellow), or null.
  const [armedCell, setArmedCell] = React.useState(null)

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

  // Reload the visible week so server-side cascade effects (recomputed leftover
  // links, cross-day changes) are reflected.
  const refetchWeek = async () => {
    const viewEnd = new Date(viewStart)
    viewEnd.setDate(viewEnd.getDate() + 6)
    const refreshed = await mealPlansApi.fetchRange(fmt(viewStart), fmt(viewEnd))
    setPlan(refreshed || {})
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

  // Extract a fresh replacement distinct from the rejected recipe, its sides,
  // and any already-chosen replacements in the same batch.
  const extractReplacement = async (meal, date, used) => {
    let replacement
    let attempts = 0
    do {
      replacement = await feedbackApi.rejectRecipe(meal.recipe, date)
      attempts += 1
    } while (
      replacement &&
      (used.has(replacement) || meal.side_recipes?.includes(replacement)) &&
      attempts < 5
    )
    if (!replacement || used.has(replacement) || meal.side_recipes?.includes(replacement)) {
      return null
    }
    used.add(replacement)
    return replacement
  }

  const handleReject = async (cell) => {
    if (!cell) return
    const { date, mealIndex } = cell
    const meal = plan[date]?.[mealIndex]
    if (!meal) return
    try {
      // A bulk source drags its leftovers with it: re-extract those slots too so
      // they don't get cascade-removed and left empty. Leftovers share the
      // source's recipe title and carry the leftover flag.
      const batch = [{ date, mealIndex, meal }]
      if (!meal.leftover) {
        Object.entries(plan).forEach(([d, meals]) => {
          meals.forEach((m, i) => {
            if (m.leftover && m.recipe === meal.recipe && !(d === date && i === mealIndex)) {
              batch.push({ date: d, mealIndex: i, meal: m })
            }
          })
        })
      }

      const used = new Set([meal.recipe])
      const replacements = []
      for (const slot of batch) {
        const replacement = await extractReplacement(slot.meal, slot.date, used)
        if (!replacement) {
          setError('No replacement recipe available.')
          return
        }
        replacements.push(replacement)
      }

      // Apply replacements locally and collect the affected days for persistence.
      const nextPlan = { ...plan }
      batch.forEach((slot, idx) => {
        nextPlan[slot.date] = nextPlan[slot.date].map((m, i) =>
          i === slot.mealIndex
            ? { ...m, recipe: replacements[idx], accepted: false, leftover: false }
            : m
        )
      })
      setPlan(nextPlan)

      const daysMap = {}
      batch.forEach((slot) => {
        daysMap[slot.date] = nextPlan[slot.date]
      })

      try {
        await persistDays(date, daysMap)
        await refetchWeek()
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
        await persistDays(date, { [date]: updatedDay })
      } catch (apiErr) {
        console.error('Failed to persist swapped meal', apiErr)
      }
    } catch (err) {
      console.error('Failed to swap meal', err)
    }
  }

  // Position-swap flow: first press arms a cell (yellow); pressing the same cell
  // again cancels; pressing a different filled cell swaps the two meals and
  // refetches the week so recomputed leftover flags/icons are reflected.
  const armSwap = async (cell) => {
    if (!cell) return
    const meal = plan[cell.date]?.[cell.mealIndex]
    if (!meal) return
    if (!armedCell) {
      setArmedCell(cell)
      return
    }
    if (armedCell.date === cell.date && armedCell.mealIndex === cell.mealIndex) {
      setArmedCell(null)
      return
    }
    const toPos = (c) => ({ plan_date: c.date, meal_number: c.mealIndex + 1 })
    const from = armedCell
    setArmedCell(null)
    try {
      await mealPlansApi.swap(toPos(from), toPos(cell))
      await refetchWeek()
    } catch (err) {
      console.error('Failed to swap meals', err)
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
    armedCell,
    armSwap,
  }
}
