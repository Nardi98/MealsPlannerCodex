/**
 * @vitest-environment jsdom
 */
import { renderHook, act, waitFor } from '@testing-library/react'
import { beforeEach, afterEach, expect, test, vi } from 'vitest'
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
