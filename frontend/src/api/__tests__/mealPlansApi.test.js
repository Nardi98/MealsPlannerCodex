import { mealPlansApi } from '../index'
import { request } from '../client'
import { vi, test, expect, afterEach } from 'vitest'

vi.mock('../client', () => ({
  request: vi.fn().mockResolvedValue({}),
}))

afterEach(() => {
  request.mockClear()
})

test('create serialises meal objects', async () => {
  await mealPlansApi.create({
    plan_date: '2024-01-01',
    plan: { '2024-01-01': [{ main: 1, side: 2 }, { main: 3 }] },
  })
  const body = JSON.parse(request.mock.calls[0][1].body)
  expect(body.plan['2024-01-01']).toEqual([
    { main_id: 1, side_id: 2 },
    { main_id: 3 },
  ])
})

test('addSide posts payload', async () => {
  await mealPlansApi.addSide('2024-01-01', 1, 2)
  expect(request).toHaveBeenCalledWith('/meal-plans/side', {
    method: 'POST',
    body: JSON.stringify({
      plan_date: '2024-01-01',
      meal_number: 1,
      side_id: 2,
    }),
  })
})
