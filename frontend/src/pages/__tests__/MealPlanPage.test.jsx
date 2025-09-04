/**
 * @vitest-environment jsdom
 */
import React from 'react'
import { render, screen, cleanup } from '@testing-library/react'
import { beforeEach, afterEach, expect, test, vi } from 'vitest'
import '@testing-library/jest-dom/vitest'
import MealPlanPage from '../MealPlanPage'
import { mealPlansApi } from '../../api/mealPlansApi'
import { tagsApi } from '../../api/tagsApi'

vi.mock('../../api/mealPlansApi', () => ({
  mealPlansApi: {
    fetchRange: vi.fn(),
    generate: vi.fn(),
    create: vi.fn(),
    accept: vi.fn(),
    addSide: vi.fn(),
    replaceSide: vi.fn(),
    removeSide: vi.fn(),
  },
}))

vi.mock('../../api/tagsApi', () => ({
  tagsApi: {
    fetchAll: vi.fn(),
  },
}))

vi.mock('../../api/feedbackApi', () => ({
  feedbackApi: {
    acceptRecipe: vi.fn(),
    rejectRecipe: vi.fn(),
  },
}))

vi.mock('../../api/recipesApi', () => ({
  recipesApi: {
    fetchAll: vi.fn(),
  },
}))

vi.mock('../../api/sideDishesApi', () => ({
  sideDishesApi: {
    generate: vi.fn(),
  },
}))

beforeEach(() => {
  const today = new Date()
  const day = today.getDay()
  const diff = day === 0 ? -6 : 1 - day
  const start = new Date(today)
  start.setDate(today.getDate() + diff)
  const startIso = start.toISOString().slice(0, 10)
  mealPlansApi.fetchRange.mockResolvedValue({
    [startIso]: [
      { recipe: 'Bulk', side_recipes: [], accepted: false, leftover: true },
    ],
  })
  tagsApi.fetchAll.mockResolvedValue([])
})

afterEach(() => {
  vi.restoreAllMocks()
  cleanup()
})

test('leftover meals display leftover icon', async () => {
  render(<MealPlanPage />)
  await screen.findByText('Bulk')
  const icon = await screen.findByAltText('Leftover')
  expect(icon).toBeInTheDocument()
})
