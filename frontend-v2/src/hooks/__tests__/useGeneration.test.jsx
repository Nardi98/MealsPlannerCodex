/**
 * @vitest-environment jsdom
 */
// Hook state and the async generate/overwrite flow. The pure param-building
// half lives in buildGenerateParams.test.js, which needs no DOM.
import { renderHook, act, waitFor } from '@testing-library/react'
import { beforeEach, afterEach, describe, expect, test, vi } from 'vitest'
import { addDays, format } from 'date-fns'
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

// Generation only accepts ranges from today on (F3).
const isoInDays = (n) => format(addDays(new Date(), n), 'yyyy-MM-dd')
const DAY = isoInDays(1)

beforeEach(() => {
  vi.clearAllMocks()
  mealPlansApi.fetchRange.mockResolvedValue({})
  mealPlansApi.generate.mockResolvedValue({
    [DAY]: [{ id: 1, title: 'Meal', leftover: false }],
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
    result.current.setForm((f) => ({ ...f, start: DAY, end: DAY }))
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
    [DAY]: [{ id: 1, title: 'Roast', leftover: false, side_ids: [7] }],
  })
  const { result } = renderHook(() => useGeneration({ setPlan: vi.fn() }))

  act(() => {
    result.current.setForm((f) => ({ ...f, start: DAY, end: DAY }))
  })
  await act(async () => {
    await result.current.handleGenerate(submit)
  })

  expect(mealPlansApi.create).toHaveBeenCalledWith(
    expect.objectContaining({
      plan: { [DAY]: [{ main_id: 1, side_ids: [7], leftover: false }] },
    }),
  )
})

test('a generated meal with no favorite sides persists an empty side list', async () => {
  mealPlansApi.generate.mockResolvedValue({
    [DAY]: [{ id: 1, title: 'Steak', leftover: false }],
  })
  const { result } = renderHook(() => useGeneration({ setPlan: vi.fn() }))

  act(() => {
    result.current.setForm((f) => ({ ...f, start: DAY, end: DAY }))
  })
  await act(async () => {
    await result.current.handleGenerate(submit)
  })

  expect(mealPlansApi.create).toHaveBeenCalledWith(
    expect.objectContaining({
      plan: { [DAY]: [{ main_id: 1, side_ids: [], leftover: false }] },
    }),
  )
})

test('generate with existing days opens the overwrite modal and defers generation', async () => {
  mealPlansApi.fetchRange.mockResolvedValueOnce({
    [DAY]: [{ recipe: 'Existing', accepted: false }],
  })
  const setPlan = vi.fn()
  const { result } = renderHook(() => useGeneration({ setPlan }))

  act(() => {
    result.current.setForm((f) => ({ ...f, start: DAY, end: DAY }))
  })
  await act(async () => {
    await result.current.handleGenerate(submit)
  })

  expect(result.current.showOverwriteModal).toBe(true)
  expect(result.current.conflictDays).toEqual([DAY])
  expect(mealPlansApi.generate).not.toHaveBeenCalled()

  await act(async () => {
    await result.current.handleConfirmOverwrite()
  })

  expect(mealPlansApi.deleteRange).toHaveBeenCalledWith(DAY, DAY)
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


describe('the plan range starts today or later (F3)', () => {
  test('the default range never starts before today', () => {
    const { result } = renderHook(() => useGeneration({ setPlan: vi.fn() }))

    expect(result.current.form.start >= isoInDays(0)).toBe(true)
    expect(result.current.form.end >= result.current.form.start).toBe(true)
  })

  test('a range starting before today is refused without asking the server', async () => {
    const { result } = renderHook(() => useGeneration({ setPlan: vi.fn() }))

    act(() => {
      result.current.setForm((f) => ({ ...f, start: isoInDays(-1), end: isoInDays(2) }))
    })
    await act(async () => {
      await result.current.handleGenerate(submit)
    })

    expect(result.current.error).toBe('Start date cannot be before today')
    expect(mealPlansApi.fetchRange).not.toHaveBeenCalled()
    expect(mealPlansApi.generate).not.toHaveBeenCalled()
  })
})
