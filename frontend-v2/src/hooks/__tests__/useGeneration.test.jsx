/**
 * @vitest-environment jsdom
 */
// Hook state and the async generate/overwrite flow. The pure param-building
// half lives in buildGenerateParams.test.js, which needs no DOM.
import { renderHook, act, waitFor } from '@testing-library/react'
import { beforeEach, afterEach, describe, expect, test, vi } from 'vitest'
import { useGeneration } from '../useGeneration'
import { mealPlansApi } from '../../api/mealPlansApi'

vi.mock('../../api/mealPlansApi', () => ({
  mealPlansApi: {
    fetchRange: vi.fn(),
    generate: vi.fn(),
    create: vi.fn(),
    deleteRange: vi.fn(),
  },
}))

const submit = { preventDefault: vi.fn() }

beforeEach(() => {
  vi.clearAllMocks()
  mealPlansApi.fetchRange.mockResolvedValue({})
  mealPlansApi.generate.mockResolvedValue({
    '2026-01-05': [{ id: 1, title: 'Meal', leftover: false }],
  })
  mealPlansApi.create.mockResolvedValue()
  mealPlansApi.deleteRange.mockResolvedValue()
})

afterEach(() => {
  vi.restoreAllMocks()
})

test('generate with no conflicts calls generate, create and updates plan', async () => {
  const setPlan = vi.fn()
  const { result } = renderHook(() => useGeneration({ setPlan }))

  act(() => {
    result.current.setForm((f) => ({ ...f, start: '2026-01-05', end: '2026-01-05' }))
  })
  await act(async () => {
    await result.current.handleGenerate(submit)
  })

  expect(mealPlansApi.generate).toHaveBeenCalledTimes(1)
  expect(mealPlansApi.create).toHaveBeenCalledTimes(1)
  expect(setPlan).toHaveBeenCalled()
  await waitFor(() => expect(result.current.message).toBe('Plan generated successfully.'))
})

test('the favorite sides chosen during generation are persisted onto the meal', async () => {
  mealPlansApi.generate.mockResolvedValue({
    '2026-01-05': [{ id: 1, title: 'Roast', leftover: false, side_ids: [7] }],
  })
  const { result } = renderHook(() => useGeneration({ setPlan: vi.fn() }))

  act(() => {
    result.current.setForm((f) => ({ ...f, start: '2026-01-05', end: '2026-01-05' }))
  })
  await act(async () => {
    await result.current.handleGenerate(submit)
  })

  expect(mealPlansApi.create).toHaveBeenCalledWith(
    expect.objectContaining({
      plan: { '2026-01-05': [{ main_id: 1, side_ids: [7], leftover: false }] },
    }),
  )
})

test('a generated meal with no favorite sides persists an empty side list', async () => {
  mealPlansApi.generate.mockResolvedValue({
    '2026-01-05': [{ id: 1, title: 'Steak', leftover: false }],
  })
  const { result } = renderHook(() => useGeneration({ setPlan: vi.fn() }))

  act(() => {
    result.current.setForm((f) => ({ ...f, start: '2026-01-05', end: '2026-01-05' }))
  })
  await act(async () => {
    await result.current.handleGenerate(submit)
  })

  expect(mealPlansApi.create).toHaveBeenCalledWith(
    expect.objectContaining({
      plan: { '2026-01-05': [{ main_id: 1, side_ids: [], leftover: false }] },
    }),
  )
})

test('generate with existing days opens the overwrite modal and defers generation', async () => {
  mealPlansApi.fetchRange.mockResolvedValueOnce({
    '2026-01-05': [{ recipe: 'Existing', accepted: false }],
  })
  const setPlan = vi.fn()
  const { result } = renderHook(() => useGeneration({ setPlan }))

  act(() => {
    result.current.setForm((f) => ({ ...f, start: '2026-01-05', end: '2026-01-05' }))
  })
  await act(async () => {
    await result.current.handleGenerate(submit)
  })

  expect(result.current.showOverwriteModal).toBe(true)
  expect(result.current.conflictDays).toEqual(['2026-01-05'])
  expect(mealPlansApi.generate).not.toHaveBeenCalled()

  await act(async () => {
    await result.current.handleConfirmOverwrite()
  })

  expect(mealPlansApi.deleteRange).toHaveBeenCalledWith('2026-01-05', '2026-01-05')
  expect(mealPlansApi.generate).toHaveBeenCalledTimes(1)
})

describe('form setters', () => {
  test('handleRangeChange updates both form.start and form.end', () => {
    const { result } = renderHook(() => useGeneration({ setPlan: () => {} }))
    act(() => {
      result.current.handleRangeChange({ start: '2024-03-04', end: '2024-03-10' })
    })
    expect(result.current.form.start).toBe('2024-03-04')
    expect(result.current.form.end).toBe('2024-03-10')
  })

  test('handleFridgeChange replaces the fridge selection', () => {
    const { result } = renderHook(() => useGeneration({ setPlan: () => {} }))
    expect(result.current.form.fridge).toEqual([])
    act(() => {
      result.current.handleFridgeChange([{ ingredient_id: 3, count: 1 }])
    })
    expect(result.current.form.fridge).toEqual([{ ingredient_id: 3, count: 1 }])
  })
})
