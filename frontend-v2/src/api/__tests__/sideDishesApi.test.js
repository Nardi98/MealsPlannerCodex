/**
 * @vitest-environment jsdom
 */
import { afterEach, expect, test, vi } from 'vitest'
import { sideDishesApi } from '../sideDishesApi'

afterEach(() => {
  vi.restoreAllMocks()
})

test('generate scores against the meal: it sends the date, meal number and exclusions', async () => {
  globalThis.fetch = vi.fn(() =>
    Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({ id: 3, title: 'Rice' }) })
  )

  const side = await sideDishesApi.generate('2026-03-10', 2, { excludeIds: [5] })

  const [url, opts] = globalThis.fetch.mock.calls[0]
  expect(url).toContain('/side-dishes/generate')
  expect(JSON.parse(opts.body)).toEqual({ plan_date: '2026-03-10', meal_number: 2, exclude_ids: [5] })
  expect(side).toEqual({ id: 3, title: 'Rice' })
})
