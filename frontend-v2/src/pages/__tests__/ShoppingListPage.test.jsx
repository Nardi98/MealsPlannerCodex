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
import { authApi } from '../../api/authApi'

vi.mock('../../api/mealPlansApi', () => ({
  mealPlansApi: {
    fetchRange: vi.fn(),
    setPeople: vi.fn(),
  },
}))

vi.mock('../../api/recipesApi', () => ({
  recipesApi: {
    fetchAll: vi.fn(),
  },
}))

vi.mock('../../api/authApi', () => ({
  authApi: {
    me: vi.fn(),
    setDefaultPeople: vi.fn(),
  },
}))

beforeEach(() => {
  const todayIso = new Date().toISOString().slice(0, 10)
  mealPlansApi.fetchRange.mockResolvedValue({
    [todayIso]: [
      { recipe: 'A', side_recipes: [], leftover: false, meal_number: 1, people: 2 },
      { recipe: 'B', side_recipes: [], leftover: true, meal_number: 2, people: 3 },
    ],
  })
  recipesApi.fetchAll.mockResolvedValue([
    { id: 1, title: 'A', ingredients: [{ name: 'ing1', amount: 1, unit: 'kg' }] },
    { id: 2, title: 'B', ingredients: [{ name: 'ing2', amount: 1, unit: 'kg' }] },
  ])
  authApi.me.mockResolvedValue({ default_people: 2 })
})

afterEach(() => {
  vi.restoreAllMocks()
  cleanup()
})

test('leftover meals are included as occurrences', async () => {
  render(<ShoppingListPage />)
  await screen.findByText('A')
  expect(screen.getByText('B')).toBeInTheDocument()
})

test('ingredient amounts are scaled by the meal people count', async () => {
  render(<ShoppingListPage />)
  // B is cooked for 3 people, so 1 kg of ing2 becomes 3 kg.
  expect(await screen.findByText('ing2: 3 kg')).toBeInTheDocument()
  // A is cooked for 2 people, so 1 kg of ing1 becomes 2 kg.
  expect(screen.getByText('ing1: 2 kg')).toBeInTheDocument()
})
