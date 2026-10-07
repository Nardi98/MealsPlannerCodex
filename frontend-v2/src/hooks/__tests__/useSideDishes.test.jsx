/**
 * @vitest-environment jsdom
 */
import { renderHook, act } from '@testing-library/react'
import React from 'react'
import { beforeEach, afterEach, expect, test, vi } from 'vitest'
import { useSideDishes } from '../useSideDishes'
import { mealPlansApi } from '../../api/mealPlansApi'
import { feedbackApi } from '../../api/feedbackApi'
import { recipesApi } from '../../api/recipesApi'
import { sideDishesApi } from '../../api/sideDishesApi'

vi.mock('../../api/mealPlansApi', () => ({
  mealPlansApi: { addSide: vi.fn(), replaceSide: vi.fn(), removeSide: vi.fn() },
}))
vi.mock('../../api/feedbackApi', () => ({
  feedbackApi: { rejectRecipe: vi.fn(), acceptRecipe: vi.fn() },
}))
vi.mock('../../api/recipesApi', () => ({
  recipesApi: { fetchAll: vi.fn() },
}))
vi.mock('../../api/sideDishesApi', () => ({
  sideDishesApi: { generate: vi.fn() },
}))

const DATE = '2026-01-05'
const cell = { date: DATE, mealIndex: 0 }

function setup(initialPlan) {
  const setError = vi.fn()
  const wrapper = renderHook(() => {
    const [plan, setPlan] = React.useState(initialPlan)
    const api = useSideDishes({ plan, setPlan, setError })
    return { plan, ...api }
  })
  return { ...wrapper, setError }
}

beforeEach(() => vi.clearAllMocks())
afterEach(() => vi.restoreAllMocks())

test('adding a side asks for one scored against the meal, then persists it', async () => {
  mealPlansApi.addSide.mockResolvedValue()
  sideDishesApi.generate.mockResolvedValue({ id: 9, title: 'Salad' })
  const { result } = setup({
    [DATE]: [{ recipe: 'Main', recipe_id: 1, side_recipes: [], side_recipe_ids: [], leftover: true, meal_number: 2 }],
  })

  await act(async () => {
    await result.current.handleAddSide(cell)
  })

  expect(sideDishesApi.generate).toHaveBeenCalledWith(DATE, 2, { excludeIds: [] })
  expect(mealPlansApi.addSide).toHaveBeenCalledWith(DATE, 2, 9, true)
  expect(result.current.plan[DATE][0].side_recipes).toEqual(['Salad'])
  expect(result.current.plan[DATE][0].side_recipe_ids).toEqual([9])
})

test('removing a side dish drops it and persists via removeSide', async () => {
  mealPlansApi.removeSide.mockResolvedValue()
  const { result } = setup({
    [DATE]: [{
      recipe: 'Main', side_recipes: ['Salad', 'Rice'], side_recipe_ids: [9, 4], leftover: false,
    }],
  })

  await act(async () => {
    await result.current.handleRemoveSide(cell, 0)
  })

  expect(mealPlansApi.removeSide).toHaveBeenCalledWith(DATE, 1, 0, false)
  expect(result.current.plan[DATE][0].side_recipes).toEqual(['Rice'])
  expect(result.current.plan[DATE][0].side_recipe_ids).toEqual([4])
})

test('rejecting a side rejects it by id and asks for a replacement for the same meal', async () => {
  mealPlansApi.replaceSide.mockResolvedValue()
  sideDishesApi.generate.mockResolvedValue({ id: 7, title: 'Beans' })
  const { result } = setup({
    [DATE]: [{
      recipe: 'Main', side_recipes: ['Salad', 'Rice'], side_recipe_ids: [9, 4], leftover: false,
    }],
  })

  await act(async () => {
    await result.current.handleRejectSide(cell, 0)
  })

  expect(feedbackApi.rejectRecipe).toHaveBeenCalledWith(9, DATE)
  expect(sideDishesApi.generate).toHaveBeenCalledWith(DATE, 1, { excludeIds: [9] })
  expect(mealPlansApi.replaceSide).toHaveBeenCalledWith(DATE, 1, 0, 7, false)
  expect(result.current.plan[DATE][0].side_recipes).toEqual(['Beans', 'Rice'])
  expect(result.current.plan[DATE][0].side_recipe_ids).toEqual([7, 4])
})

test('rejecting a side dish keeps it when no replacement is available', async () => {
  sideDishesApi.generate.mockRejectedValue(new Error('No side dishes available'))
  const { result, setError } = setup({
    [DATE]: [{ recipe: 'Main', side_recipes: ['Salad'], side_recipe_ids: [9], leftover: false }],
  })

  await act(async () => {
    await result.current.handleRejectSide(cell, 0)
  })

  expect(mealPlansApi.replaceSide).not.toHaveBeenCalled()
  expect(setError).toHaveBeenCalledWith('No replacement recipe available.')
  expect(result.current.plan[DATE][0].side_recipes).toEqual(['Salad'])
})

test('swapping a side by hand sends feedback by id for the old and the new one', async () => {
  mealPlansApi.replaceSide.mockResolvedValue()
  recipesApi.fetchAll.mockResolvedValue([{ id: 9, title: 'Salad' }, { id: 3, title: 'Slaw' }])
  const { result } = setup({
    [DATE]: [{ recipe: 'Main', side_recipes: ['Salad'], side_recipe_ids: [9], leftover: false }],
  })

  await act(async () => {
    await result.current.handleSwapSide(cell, 0, 'Slaw')
  })

  expect(feedbackApi.rejectRecipe).toHaveBeenCalledWith(9, DATE)
  expect(feedbackApi.acceptRecipe).toHaveBeenCalledWith(3, DATE)
  expect(mealPlansApi.replaceSide).toHaveBeenCalledWith(DATE, 1, 0, 3, false)
  expect(result.current.plan[DATE][0].side_recipe_ids).toEqual([3])
})
