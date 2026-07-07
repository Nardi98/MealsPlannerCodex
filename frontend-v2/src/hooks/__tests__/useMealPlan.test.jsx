/**
 * @vitest-environment jsdom
 */
import { renderHook, act, waitFor } from '@testing-library/react'
import { beforeEach, afterEach, expect, test, vi } from 'vitest'
import { useMealPlan } from '../useMealPlan'
import { mealPlansApi } from '../../api/mealPlansApi'
import { feedbackApi } from '../../api/feedbackApi'
import { recipesApi } from '../../api/recipesApi'

vi.mock('../../api/mealPlansApi', () => ({
  mealPlansApi: {
    fetchRange: vi.fn(),
    create: vi.fn(),
    accept: vi.fn(),
  },
}))
vi.mock('../../api/feedbackApi', () => ({
  feedbackApi: { acceptRecipe: vi.fn(), rejectRecipe: vi.fn() },
}))
vi.mock('../../api/recipesApi', () => ({
  recipesApi: { fetchAll: vi.fn() },
}))

let startIso
beforeEach(() => {
  vi.clearAllMocks()
  const today = new Date()
  const day = today.getDay()
  const diff = day === 0 ? -6 : 1 - day
  const start = new Date(today)
  start.setDate(today.getDate() + diff)
  startIso = start.toISOString().slice(0, 10)
  mealPlansApi.fetchRange.mockResolvedValue({
    [startIso]: [{ recipe: 'Bulk', side_recipes: [], accepted: false, leftover: true }],
  })
  mealPlansApi.create.mockResolvedValue()
  mealPlansApi.accept.mockResolvedValue()
  feedbackApi.acceptRecipe.mockResolvedValue()
})

afterEach(() => vi.restoreAllMocks())

test('loads the current week plan on mount', async () => {
  const { result } = renderHook(() => useMealPlan({ setError: vi.fn() }))
  await waitFor(() => expect(result.current.plan[startIso]).toBeDefined())
  expect(result.current.weekDays).toHaveLength(7)
})

test('accepting a meal marks it accepted and sends feedback', async () => {
  const { result } = renderHook(() => useMealPlan({ setError: vi.fn() }))
  await waitFor(() => expect(result.current.plan[startIso]).toBeDefined())

  await act(async () => {
    await result.current.handleAccept({ date: startIso, mealIndex: 0 })
  })

  expect(mealPlansApi.accept).toHaveBeenCalledWith(startIso, 1, true)
  expect(feedbackApi.acceptRecipe).toHaveBeenCalledWith('Bulk', startIso)
  expect(result.current.plan[startIso][0].accepted).toBe(true)
})

test('rejecting a leftover meal clears the leftover flag for the replacement', async () => {
  feedbackApi.rejectRecipe.mockResolvedValue('Replacement')
  recipesApi.fetchAll.mockResolvedValue([
    { id: 1, title: 'Bulk' },
    { id: 2, title: 'Replacement' },
  ])
  const { result } = renderHook(() => useMealPlan({ setError: vi.fn() }))
  await waitFor(() => expect(result.current.plan[startIso]).toBeDefined())

  await act(async () => {
    await result.current.handleReject({ date: startIso, mealIndex: 0 })
  })

  await waitFor(() =>
    expect(mealPlansApi.create).toHaveBeenCalledWith({
      plan_date: startIso,
      plan: { [startIso]: [{ main_id: 2, side_ids: [], leftover: false }] },
    })
  )
  expect(result.current.plan[startIso][0].leftover).toBe(false)
})
