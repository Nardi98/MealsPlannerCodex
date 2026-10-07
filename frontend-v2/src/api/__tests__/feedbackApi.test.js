/**
 * @vitest-environment jsdom
 */
import { afterEach, expect, test, vi } from 'vitest'
import { feedbackApi } from '../feedbackApi'

afterEach(() => {
  vi.restoreAllMocks()
})

const respondWith = (body) => {
  globalThis.fetch = vi.fn(() =>
    Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(body) })
  )
}

const sentBody = () => JSON.parse(globalThis.fetch.mock.calls[0][1].body)

test('acceptRecipe posts the recipe id and the slot date', async () => {
  respondWith({ status: 'ok' })

  await feedbackApi.acceptRecipe(4, '2024-01-01')

  expect(globalThis.fetch.mock.calls[0][0]).toContain('/feedback/accept')
  expect(sentBody()).toEqual({ recipe_id: 4, plan_date: '2024-01-01', leftover: false })
})

test('acceptRecipe flags a leftover so the score is not bumped twice', async () => {
  respondWith({ status: 'ok' })

  await feedbackApi.acceptRecipe(4, '2024-01-01', { leftover: true })

  expect(sentBody()).toEqual({ recipe_id: 4, plan_date: '2024-01-01', leftover: true })
})

test('rejectRecipe posts the recipe id and the slot date', async () => {
  respondWith({ status: 'ok' })

  await feedbackApi.rejectRecipe(7, '2024-01-02')

  expect(globalThis.fetch.mock.calls[0][0]).toContain('/feedback/reject')
  expect(sentBody()).toEqual({ recipe_id: 7, plan_date: '2024-01-02' })
})
