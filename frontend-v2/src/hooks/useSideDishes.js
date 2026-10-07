import { mealPlansApi } from '../api/mealPlansApi'
import { feedbackApi } from '../api/feedbackApi'
import { sideDishesApi } from '../api/sideDishesApi'
import { idOfTitle, mealNumberOf } from './useMealPlan'

/**
 * Per-meal side-dish actions (add / reject / remove / swap). Each handler takes
 * an explicit `cell` ({ date, mealIndex }) so the page can drive them from the
 * active cell. Mutates the shared plan via the provided `setPlan`, keeping a
 * meal's `side_recipes` titles and `side_recipe_ids` in step.
 */
export function useSideDishes({ plan, setPlan, setError }) {
  const updateSides = (date, mealIndex, mapper) =>
    setPlan((p) => ({
      ...p,
      [date]: p[date].map((m, i) => {
        if (i !== mealIndex) return m
        const titles = m.side_recipes || []
        const sides = mapper(titles.map((title, idx) => ({ title, id: m.side_recipe_ids?.[idx] })))
        return {
          ...m,
          side_recipes: sides.map((s) => s.title),
          side_recipe_ids: sides.map((s) => s.id),
        }
      }),
    }))

  const handleAddSide = async (cell) => {
    if (!cell) return
    const { date, mealIndex } = cell
    const meal = plan[date]?.[mealIndex]
    if (!meal) return
    const mealNumber = mealNumberOf(meal, mealIndex)
    try {
      // Scored against this meal's date; the server leaves out the sides
      // already on the plate.
      const generated = await sideDishesApi.generate(date, mealNumber, {
        excludeIds: meal.side_recipe_ids || [],
      })
      if (!generated) {
        setError('No unique side dish available.')
        return
      }
      await mealPlansApi.addSide(date, mealNumber, generated.id, meal.leftover)
      updateSides(date, mealIndex, (sides) => [...sides, generated])
    } catch (err) {
      console.error('Failed to add side dish', err)
      setError('No unique side dish available.')
    }
  }

  const handleRejectSide = async (cell, sideIndex) => {
    if (!cell) return
    const { date, mealIndex } = cell
    const meal = plan[date]?.[mealIndex]
    const currentId = meal?.side_recipe_ids?.[sideIndex]
    if (!meal || !currentId) return
    const mealNumber = mealNumberOf(meal, mealIndex)
    try {
      // The rejection bans the side from this date on; it is still on the
      // plate, so the server would skip it anyway, but saying so is explicit.
      await feedbackApi.rejectRecipe(currentId, date)
      const replacement = await sideDishesApi.generate(date, mealNumber, {
        excludeIds: [currentId],
      })
      if (!replacement) {
        setError('No replacement recipe available.')
        return
      }
      await mealPlansApi.replaceSide(date, mealNumber, sideIndex, replacement.id, meal.leftover)
      updateSides(date, mealIndex, (sides) =>
        sides.map((s, idx) => (idx === sideIndex ? replacement : s))
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
      await mealPlansApi.removeSide(date, mealNumberOf(meal, mealIndex), sideIndex, meal.leftover)
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
    const oldId = meal?.side_recipe_ids?.[sideIndex]
    if (!meal || !oldId) return
    const existing = meal.side_recipes.filter((_, idx) => idx !== sideIndex)
    if (newTitle === meal.recipe || existing.includes(newTitle)) {
      setError('Side dish already present.')
      return
    }
    try {
      const newId = await idOfTitle(newTitle)
      if (!newId) {
        setError('Replacement recipe not found.')
        return
      }
      await Promise.all([
        feedbackApi.rejectRecipe(oldId, date),
        feedbackApi.acceptRecipe(newId, date),
      ])
      await mealPlansApi.replaceSide(date, mealNumberOf(meal, mealIndex), sideIndex, newId, meal.leftover)
      updateSides(date, mealIndex, (sides) =>
        sides.map((s, idx) => (idx === sideIndex ? { id: newId, title: newTitle } : s))
      )
    } catch (err) {
      console.error('Failed to swap side dish', err)
    }
  }

  return { handleAddSide, handleRejectSide, handleRemoveSide, handleSwapSide }
}
