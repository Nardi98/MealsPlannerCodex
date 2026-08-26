/**
 * @vitest-environment jsdom
 */
import { afterEach, expect, test, vi } from 'vitest'
import { mealPlansApi } from '../mealPlansApi'

afterEach(() => {
  vi.restoreAllMocks()
})

const respondWith = (body) => {
  globalThis.fetch = vi.fn(() =>
    Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(body) })
  )
}

test('fetchRange strips the "(leftover)" suffix into the leftover flag', async () => {
  respondWith({
    '2026-08-24': [{ recipe: 'Stew (leftover)', side_recipes: [], meal_number: 1 }],
  })

  const plan = await mealPlansApi.fetchRange('2026-08-24', '2026-08-24')

  expect(plan['2026-08-24'][0].recipe).toBe('Stew')
  expect(plan['2026-08-24'][0].leftover).toBe(true)
})

test('fetchRange passes an empty slot through as null', async () => {
  // A day is indexed by meal_number, so a slot whose recipe was deleted arrives
  // as a null. Parsing it as a meal throws and blanks the entire plan.
  respondWith({
    '2026-08-24': [null, { recipe: 'Dinner', side_recipes: [], meal_number: 2 }],
  })

  const plan = await mealPlansApi.fetchRange('2026-08-24', '2026-08-24')

  expect(plan['2026-08-24'][0]).toBeNull()
  expect(plan['2026-08-24'][1].recipe).toBe('Dinner')
})
