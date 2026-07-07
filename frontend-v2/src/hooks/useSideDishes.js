import { mealPlansApi } from '../api/mealPlansApi'
import { feedbackApi } from '../api/feedbackApi'
import { recipesApi } from '../api/recipesApi'
import { sideDishesApi } from '../api/sideDishesApi'

/**
 * Per-meal side-dish actions (add / reject / remove / swap). Each handler takes
 * an explicit `cell` ({ date, mealIndex }) so the page can drive them from the
 * active cell. Mutates the shared plan via the provided `setPlan`.
 */
export function useSideDishes({ plan, setPlan, setError }) {
  const updateSides = (date, mealIndex, mapper) =>
    setPlan((p) => ({
      ...p,
      [date]: p[date].map((m, i) =>
        i === mealIndex ? { ...m, side_recipes: mapper(m.side_recipes || []) } : m
      ),
    }))

  const handleAddSide = async (cell) => {
    if (!cell) return
    const { date, mealIndex } = cell
    const meal = plan[date]?.[mealIndex]
    if (!meal) return
    try {
      const existing = meal.side_recipes || []
      const avoid = [meal.recipe, ...existing]
      const generated = await sideDishesApi.generate({ avoid_titles: avoid })
      if (!generated) {
        setError('No unique side dish available.')
        return
      }
      const { id, title } = generated
      await mealPlansApi.addSide(date, mealIndex + 1, id, meal.leftover)
      updateSides(date, mealIndex, (sides) => [...sides, title])
    } catch (err) {
      console.error('Failed to add side dish', err)
      setError('No unique side dish available.')
    }
  }

  const handleRejectSide = async (cell, sideIndex) => {
    if (!cell) return
    const { date, mealIndex } = cell
    const meal = plan[date]?.[mealIndex]
    const current = meal?.side_recipes?.[sideIndex]
    if (!meal || !current) return
    const existing = meal.side_recipes.filter((_, idx) => idx !== sideIndex)
    try {
      await feedbackApi.rejectRecipe(current, date)
      const avoid = [meal.recipe, ...existing]
      const replacement = await sideDishesApi.generate({ avoid_titles: avoid })
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
      updateSides(date, mealIndex, (sides) =>
        sides.map((s, idx) => (idx === sideIndex ? replacement.title : s))
      )
    } catch (err) {
      console.error('Failed to reject side dish', err)
      setError('No replacement recipe available.')
    }
  }

  const handleRemoveSide = async (cell, sideIndex) => {
    if (!cell) return
    const { date, mealIndex } = cell
    const meal = plan[date]?.[mealIndex]
    if (!meal) return
    try {
      await mealPlansApi.removeSide(date, mealIndex + 1, sideIndex, meal.leftover)
      updateSides(date, mealIndex, (sides) =>
        sides.filter((_, idx) => idx !== sideIndex)
      )
    } catch (err) {
      console.error('Failed to remove side dish', err)
    }
  }

  const handleSwapSide = async (cell, sideIndex, newTitle) => {
    if (!cell) return
    const { date, mealIndex } = cell
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
      await mealPlansApi.replaceSide(date, mealIndex + 1, sideIndex, newId, meal.leftover)
      updateSides(date, mealIndex, (sides) =>
        sides.map((s, idx) => (idx === sideIndex ? newTitle : s))
      )
    } catch (err) {
      console.error('Failed to swap side dish', err)
    }
  }

  return { handleAddSide, handleRejectSide, handleRemoveSide, handleSwapSide }
}
