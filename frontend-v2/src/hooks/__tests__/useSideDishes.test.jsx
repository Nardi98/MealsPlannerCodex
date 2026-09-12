/**
 * @vitest-environment jsdom
 */
import { renderHook, act } from '@testing-library/react'
import React from 'react'
import { beforeEach, afterEach, expect, test, vi } from 'vitest'
import { useSideDishes } from '../useSideDishes'
import { mealPlansApi } from '../../api/mealPlansApi'
import { sideDishesApi } from '../../api/sideDishesApi'

vi.mock('../../api/mealPlansApi', () => ({
  mealPlansApi: { addSide: vi.fn(), replaceSide: vi.fn(), removeSide: vi.fn() },
}))
vi.mock('../../api/feedbackApi', () => ({
  feedbackApi: { rejectRecipe: vi.fn(), acceptRecipe: vi.fn() },
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

test('adding a side dish appends it and persists via addSide', async () => {
  mealPlansApi.addSide.mockResolvedValue()
  sideDishesApi.generate.mockResolvedValue({ id: 9, title: 'Salad' })
  const { result } = setup({ [DATE]: [{ recipe: 'Main', side_recipes: [], leftover: true }] })

  await act(async () => {
    await result.current.handleAddSide(cell)
  })

  expect(mealPlansApi.addSide).toHaveBeenCalledWith(DATE, 1, 9, true)
  expect(result.current.plan[DATE][0].side_recipes).toEqual(['Salad'])
})

test('removing a side dish drops it and persists via removeSide', async () => {
  mealPlansApi.removeSide.mockResolvedValue()
  const { result } = setup({
    [DATE]: [{ recipe: 'Main', side_recipes: ['Salad', 'Rice'], leftover: false }],
  })

  await act(async () => {
    await result.current.handleRemoveSide(cell, 0)
  })

  expect(mealPlansApi.removeSide).toHaveBeenCalledWith(DATE, 1, 0, false)
  expect(result.current.plan[DATE][0].side_recipes).toEqual(['Rice'])
})

test('rejecting a side dish asks for a replacement that is not the rejected one', async () => {
  mealPlansApi.replaceSide.mockResolvedValue()
  sideDishesApi.generate.mockResolvedValue({ id: 7, title: 'Beans' })
  const { result } = setup({
    [DATE]: [{ recipe: 'Main', side_recipes: ['Salad', 'Rice'], leftover: false }],
  })

  await act(async () => {
    await result.current.handleRejectSide(cell, 0)
  })

  const { avoid_titles: avoided } = sideDishesApi.generate.mock.calls[0][0]
  expect(avoided).toContain('Salad')
  expect(avoided).toEqual(expect.arrayContaining(['Main', 'Rice']))
  expect(result.current.plan[DATE][0].side_recipes).toEqual(['Beans', 'Rice'])
})

test('rejecting a side dish keeps it when no replacement is available', async () => {
  sideDishesApi.generate.mockRejectedValue(new Error('No side dishes available'))
  const { result, setError } = setup({
    [DATE]: [{ recipe: 'Main', side_recipes: ['Salad'], leftover: false }],
  })

  await act(async () => {
    await result.current.handleRejectSide(cell, 0)
  })

  expect(mealPlansApi.replaceSide).not.toHaveBeenCalled()
  expect(setError).toHaveBeenCalledWith('No replacement recipe available.')
  expect(result.current.plan[DATE][0].side_recipes).toEqual(['Salad'])
})
