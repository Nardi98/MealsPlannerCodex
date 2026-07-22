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
    swap: vi.fn(),
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
  mealPlansApi.swap.mockResolvedValue()
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
  // Mount fetch returns the leftover; the post-reject refetch returns the replacement.
  mealPlansApi.fetchRange
    .mockResolvedValueOnce({
      [startIso]: [{ recipe: 'Bulk', side_recipes: [], accepted: false, leftover: true }],
    })
    .mockResolvedValueOnce({
      [startIso]: [{ recipe: 'Replacement', side_recipes: [], accepted: false, leftover: false }],
    })
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

test('rejecting a meal refetches the week to reflect server-side changes', async () => {
  feedbackApi.rejectRecipe.mockResolvedValue('Replacement')
  recipesApi.fetchAll.mockResolvedValue([
    { id: 1, title: 'Solo' },
    { id: 2, title: 'Replacement' },
  ])
  // A plain meal with no leftovers; the post-reject refetch is the source of truth.
  mealPlansApi.fetchRange
    .mockResolvedValueOnce({
      [startIso]: [{ recipe: 'Solo', side_recipes: [], accepted: false, leftover: false }],
    })
    .mockResolvedValueOnce({
      [startIso]: [{ recipe: 'Replacement', side_recipes: [], accepted: false, leftover: false }],
    })
  const { result } = renderHook(() => useMealPlan({ setError: vi.fn() }))
  await waitFor(() => expect(result.current.plan[startIso]).toBeDefined())

  await act(async () => {
    await result.current.handleReject({ date: startIso, mealIndex: 0 })
  })

  await waitFor(() => expect(mealPlansApi.fetchRange).toHaveBeenCalledTimes(2))
  expect(result.current.plan[startIso][0].recipe).toBe('Replacement')
})

test('arming a cell sets armedCell without calling swap', async () => {
  const { result } = renderHook(() => useMealPlan({ setError: vi.fn() }))
  await waitFor(() => expect(result.current.plan[startIso]).toBeDefined())

  await act(async () => {
    await result.current.armSwap({ date: startIso, mealIndex: 0 })
  })

  expect(result.current.armedCell).toEqual({ date: startIso, mealIndex: 0 })
  expect(mealPlansApi.swap).not.toHaveBeenCalled()
})

test('arming the same cell again cancels (disarms)', async () => {
  const { result } = renderHook(() => useMealPlan({ setError: vi.fn() }))
  await waitFor(() => expect(result.current.plan[startIso]).toBeDefined())

  await act(async () => {
    await result.current.armSwap({ date: startIso, mealIndex: 0 })
  })
  await act(async () => {
    await result.current.armSwap({ date: startIso, mealIndex: 0 })
  })

  expect(result.current.armedCell).toBeNull()
  expect(mealPlansApi.swap).not.toHaveBeenCalled()
})

test('arming a second cell swaps the two meals and refetches', async () => {
  const day2 = new Date(startIso)
  day2.setDate(day2.getDate() + 1)
  const day2Iso = day2.toISOString().slice(0, 10)
  mealPlansApi.fetchRange
    .mockResolvedValueOnce({
      [startIso]: [{ recipe: 'A', side_recipes: [], accepted: false, leftover: false }],
      [day2Iso]: [{ recipe: 'B', side_recipes: [], accepted: false, leftover: false }],
    })
    .mockResolvedValueOnce({
      [startIso]: [{ recipe: 'B', side_recipes: [], accepted: false, leftover: false }],
      [day2Iso]: [{ recipe: 'A', side_recipes: [], accepted: false, leftover: false }],
    })
  const { result } = renderHook(() => useMealPlan({ setError: vi.fn() }))
  await waitFor(() => expect(result.current.plan[day2Iso]).toBeDefined())

  await act(async () => {
    await result.current.armSwap({ date: startIso, mealIndex: 0 })
  })
  await act(async () => {
    await result.current.armSwap({ date: day2Iso, mealIndex: 0 })
  })

  expect(mealPlansApi.swap).toHaveBeenCalledWith(
    { plan_date: startIso, meal_number: 1 },
    { plan_date: day2Iso, meal_number: 1 },
  )
  expect(result.current.armedCell).toBeNull()
  await waitFor(() => expect(result.current.plan[startIso][0].recipe).toBe('B'))
})

test('rejecting a bulk source re-extracts its leftover slots as fresh meals', async () => {
  recipesApi.fetchAll.mockResolvedValue([
    { id: 1, title: 'Bulk' },
    { id: 2, title: 'NewSource' },
    { id: 3, title: 'NewLeftover' },
  ])
  feedbackApi.rejectRecipe
    .mockResolvedValueOnce('NewSource')
    .mockResolvedValueOnce('NewLeftover')
  const day2 = new Date(startIso)
  day2.setDate(day2.getDate() + 1)
  const day2Iso = day2.toISOString().slice(0, 10)
  mealPlansApi.fetchRange
    .mockResolvedValueOnce({
      [startIso]: [{ recipe: 'Bulk', side_recipes: [], accepted: false, leftover: false }],
      [day2Iso]: [{ recipe: 'Bulk', side_recipes: [], accepted: false, leftover: true }],
    })
    .mockResolvedValueOnce({
      [startIso]: [{ recipe: 'NewSource', side_recipes: [], accepted: false, leftover: false }],
      [day2Iso]: [{ recipe: 'NewLeftover', side_recipes: [], accepted: false, leftover: false }],
    })
  const { result } = renderHook(() => useMealPlan({ setError: vi.fn() }))
  await waitFor(() => expect(result.current.plan[day2Iso]).toBeDefined())

  await act(async () => {
    await result.current.handleReject({ date: startIso, mealIndex: 0 })
  })

  await waitFor(() => expect(mealPlansApi.create).toHaveBeenCalled())
  const payload = mealPlansApi.create.mock.calls[0][0]
  // Both the source slot and its leftover slot get fresh, non-leftover recipes.
  expect(payload.plan[startIso][0]).toEqual({ main_id: 2, side_ids: [], leftover: false })
  expect(payload.plan[day2Iso][0]).toEqual({ main_id: 3, side_ids: [], leftover: false })
})
