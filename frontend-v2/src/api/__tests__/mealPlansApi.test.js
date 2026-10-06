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

test('fetchRange takes the leftover flag from the field the server sends', async () => {
  respondWith({
    '2026-08-24': [
      { recipe: 'Stew', side_recipes: [], meal_number: 1, leftover: true },
      { recipe: 'Soup', side_recipes: [], meal_number: 2, leftover: false },
    ],
  })

  const plan = await mealPlansApi.fetchRange('2026-08-24', '2026-08-24')

  expect(plan['2026-08-24'][0].leftover).toBe(true)
  expect(plan['2026-08-24'][1].leftover).toBe(false)
})

test('fetchRange leaves a title ending in "(leftover)" alone', async () => {
  // The server sends the raw title and a separate `leftover` field
  // (crud.meal_item), so a title is never state to be parsed.
  respondWith({
    '2026-08-24': [
      { recipe: 'Stew (leftover)', side_recipes: [], meal_number: 1, leftover: false },
    ],
  })

  const plan = await mealPlansApi.fetchRange('2026-08-24', '2026-08-24')

  expect(plan['2026-08-24'][0].recipe).toBe('Stew (leftover)')
  expect(plan['2026-08-24'][0].leftover).toBe(false)
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

// `VITE_API_BASE_URL` is set in .env, so fetch receives an absolute URL. Compare
// on path+query alone so these tests hold whatever the base is configured to.
const fetchedPaths = () =>
  globalThis.fetch.mock.calls.map(([url]) => {
    const { pathname, search } = new URL(url, 'http://base.invalid')
    return `${pathname}${search}`
  })

const isLegacyPlanPath = (p) => p === '/plan' || p.startsWith('/plan?')

test('fetchRange requests the /meal-plans path', async () => {
  respondWith({})

  await mealPlansApi.fetchRange('2026-08-24', '2026-08-31')

  expect(fetchedPaths()).toEqual([
    '/meal-plans?start_date=2026-08-24&end_date=2026-08-31',
  ])
})

test('create posts to /meal-plans, and carries force through', async () => {
  respondWith({})

  await mealPlansApi.create({ plan: {} })
  await mealPlansApi.create({ plan: {} }, { force: true })

  expect(fetchedPaths()).toEqual(['/meal-plans', '/meal-plans?force=true'])
  expect(globalThis.fetch.mock.calls[0][1]).toMatchObject({ method: 'POST' })
})

test('deleteRange deletes on the /meal-plans path', async () => {
  respondWith({ deleted: 0 })

  await mealPlansApi.deleteRange('2026-08-24', '2026-08-31')

  expect(fetchedPaths()).toEqual([
    '/meal-plans?start_date=2026-08-24&end_date=2026-08-31',
  ])
  expect(globalThis.fetch.mock.calls[0][1]).toMatchObject({ method: 'DELETE' })
})

test('no mealPlansApi method addresses the legacy /plan path', async () => {
  // Guards the migration against regressing. `/plan/settings` is a different,
  // current endpoint and belongs to planSettingsApi, so it must not match here.
  respondWith({})

  await mealPlansApi.fetchRange('2026-08-24', '2026-08-24')
  await mealPlansApi.create({ plan: {} })
  await mealPlansApi.deleteRange('2026-08-24', '2026-08-24')

  expect(fetchedPaths()).toHaveLength(3)
  expect(fetchedPaths().filter(isLegacyPlanPath)).toEqual([])
})

test('the legacy-path guard would catch a regression', async () => {
  // Proves the guard above can fail: without this, a base-URL change could make
  // `isLegacyPlanPath` silently match nothing and the guard pass vacuously.
  expect(isLegacyPlanPath('/plan')).toBe(true)
  expect(isLegacyPlanPath('/plan?start_date=2026-08-24')).toBe(true)
  expect(isLegacyPlanPath('/plan/settings')).toBe(false)
  expect(isLegacyPlanPath('/meal-plans')).toBe(false)
})
