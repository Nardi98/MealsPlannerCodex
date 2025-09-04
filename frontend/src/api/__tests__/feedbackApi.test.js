/**
 * @vitest-environment jsdom
 */
import { afterEach, expect, test, vi } from 'vitest'
import { feedbackApi } from '../feedbackApi'

afterEach(() => {
  vi.restoreAllMocks()
})

test('acceptRecipe posts title and consumed_date', async () => {
  globalThis.fetch = vi.fn(() =>
    Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({}) })
  )

  await feedbackApi.acceptRecipe('Test', '2024-01-01')

  const [url, opts] = globalThis.fetch.mock.calls[0]
  expect(url).toContain('/feedback/accept')
  expect(opts).toEqual({
    method: 'POST',
    body: JSON.stringify({ title: 'Test', consumed_date: '2024-01-01' }),
    headers: { 'Content-Type': 'application/json' },
  })
})

test('rejectRecipe posts title and consumed_date', async () => {
  globalThis.fetch = vi.fn(() =>
    Promise.resolve({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ replacement: 'Alt' }),
    })
  )

  const result = await feedbackApi.rejectRecipe('Bad', '2024-01-02')

  const [url, opts] = globalThis.fetch.mock.calls[0]
  expect(url).toContain('/feedback/reject')
  expect(opts).toEqual({
    method: 'POST',
    body: JSON.stringify({ title: 'Bad', consumed_date: '2024-01-02' }),
    headers: { 'Content-Type': 'application/json' },
  })
  expect(result).toBe('Alt')
})
