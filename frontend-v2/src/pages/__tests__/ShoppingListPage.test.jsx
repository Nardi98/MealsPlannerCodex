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

test('a day with an empty lunch slot still builds a list', async () => {
  // The backend serves a day as an array indexed by meal_number, so a slot with
  // no meal arrives as a null the page must skip rather than dereference.
  const todayIso = new Date().toISOString().slice(0, 10)
  mealPlansApi.fetchRange.mockResolvedValue({
    [todayIso]: [
      null,
      { recipe: 'B', side_recipes: [], leftover: false, meal_number: 2, people: 2 },
    ],
  })

  render(<ShoppingListPage />)

  expect(await screen.findByText('B')).toBeInTheDocument()
})


// --- the recipe's own servings basis ----------------------------------------

test('ingredient amounts are divided by the basis the recipe was written for', async () => {
  const todayIso = new Date().toISOString().slice(0, 10)
  mealPlansApi.fetchRange.mockResolvedValue({
    [todayIso]: [
      { recipe: 'A', side_recipes: [], leftover: false, meal_number: 1, people: 2 },
    ],
  })
  recipesApi.fetchAll.mockResolvedValue([
    {
      id: 1,
      title: 'A',
      servings: 4,
      ingredients: [{ name: 'ing1', amount: 800, unit: 'g' }],
    },
  ])

  render(<ShoppingListPage />)

  // Written for 4, cooked for 2: half the recipe.
  expect(await screen.findByText('ing1: 400 g')).toBeInTheDocument()
})

test('an occurrence cooking part of a recipe says so', async () => {
  const todayIso = new Date().toISOString().slice(0, 10)
  mealPlansApi.fetchRange.mockResolvedValue({
    [todayIso]: [
      { recipe: 'A', side_recipes: ['S'], leftover: false, meal_number: 1, people: 2 },
    ],
  })
  recipesApi.fetchAll.mockResolvedValue([
    { id: 1, title: 'A', servings: 4, ingredients: [] },
    { id: 2, title: 'S', servings: 1, ingredients: [] },
  ])

  render(<ShoppingListPage />)

  expect(await screen.findByText('×½')).toBeInTheDocument()
  // The side is written for one, so two people means two of it.
  expect(screen.getByText('×2')).toBeInTheDocument()
})

test('an occurrence cooking exactly one batch is not annotated', async () => {
  const todayIso = new Date().toISOString().slice(0, 10)
  mealPlansApi.fetchRange.mockResolvedValue({
    [todayIso]: [
      { recipe: 'A', side_recipes: [], leftover: false, meal_number: 1, people: 4 },
    ],
  })
  recipesApi.fetchAll.mockResolvedValue([
    { id: 1, title: 'A', servings: 4, ingredients: [] },
  ])

  render(<ShoppingListPage />)

  await screen.findByText('A')
  expect(screen.queryByText(/^×/)).toBeNull()
})
