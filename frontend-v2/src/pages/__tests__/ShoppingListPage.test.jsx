/**
 * @vitest-environment jsdom
 */
import React from 'react'
import { render, screen, cleanup } from '@testing-library/react'
import { beforeEach, afterEach, expect, test, vi } from 'vitest'
import '@testing-library/jest-dom/vitest'
import ShoppingListPage from '../ShoppingListPage'
import { mealPlansApi } from '../../api/mealPlansApi'
import { recipesApi } from '../../api/recipesApi'

vi.mock('../../api/mealPlansApi', () => ({
  mealPlansApi: {
    fetchRange: vi.fn(),
  },
}))

vi.mock('../../api/recipesApi', () => ({
  recipesApi: {
    fetchAll: vi.fn(),
  },
}))

beforeEach(() => {
  const todayIso = new Date().toISOString().slice(0, 10)
  mealPlansApi.fetchRange.mockResolvedValue({
    [todayIso]: [
      { recipe: 'A', side_recipes: [], leftover: false },
      { recipe: 'B', side_recipes: [], leftover: true },
    ],
  })
  recipesApi.fetchAll.mockResolvedValue([
    { id: 1, title: 'A', ingredients: [{ name: 'ing1' }] },
    { id: 2, title: 'B', ingredients: [{ name: 'ing2' }] },
  ])
})

afterEach(() => {
  vi.restoreAllMocks()
  cleanup()
})

test('leftover meals are excluded from shopping list', async () => {
  render(<ShoppingListPage />)
  await screen.findByText('A')
  expect(screen.queryByText('B')).toBeNull()
})
