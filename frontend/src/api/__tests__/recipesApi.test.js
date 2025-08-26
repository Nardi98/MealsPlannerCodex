import { recipesApi } from '../index'
import { request } from '../client'
import { vi, test, expect } from 'vitest'

vi.mock('../client', () => ({
  request: vi.fn().mockResolvedValue({}),
}))

test('ingredient without season submits all months', async () => {
  await recipesApi.create({
    title: 'Test',
    course: 'main',
    servings_default: 1,
    ingredients: [
      { name: 'pepper', quantity: 1, unit: 'piece', season: [] },
    ],
  })
  const body = JSON.parse(request.mock.calls[0][1].body)
  expect(body.ingredients[0].season_months).toEqual([
    1,2,3,4,5,6,7,8,9,10,11,12,
  ])
})
