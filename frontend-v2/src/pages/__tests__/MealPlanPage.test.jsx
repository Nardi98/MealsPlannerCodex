/**
 * @vitest-environment jsdom
 */
import React from 'react'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
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
    deleteRange: vi.fn(),
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
  mealPlansApi.deleteRange.mockResolvedValue()
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

test('regeneration waits for overwrite confirmation before proceeding', async () => {
  const user = userEvent.setup()
  const today = new Date()
  const day = today.getDay()
  const diff = day === 0 ? -6 : 1 - day
  const start = new Date(today)
  start.setDate(today.getDate() + diff)
  const startIso = start.toISOString().slice(0, 10)
  const end = new Date(start)
  end.setDate(start.getDate() + 6)
  const endIso = end.toISOString().slice(0, 10)

  mealPlansApi.fetchRange.mockReset()
  mealPlansApi.generate.mockReset()
  mealPlansApi.create.mockReset()
  mealPlansApi.deleteRange.mockReset()
  mealPlansApi.fetchRange
    .mockResolvedValueOnce({
      [startIso]: [
        { recipe: 'Bulk', side_recipes: [], accepted: false, leftover: true },
      ],
    })
    .mockResolvedValueOnce({
      [startIso]: [
        { recipe: 'Existing', side_recipes: [], accepted: false, leftover: false },
      ],
    })
    .mockResolvedValueOnce({})

  mealPlansApi.generate.mockResolvedValue({
    [startIso]: [{ id: 1, title: 'Generated Meal', leftover: false }],
  })
  mealPlansApi.create.mockResolvedValue()
  mealPlansApi.deleteRange.mockResolvedValue()

  render(<MealPlanPage />)

  await screen.findByText('Bulk')

  await user.click(screen.getByRole('button', { name: /generate plan/i }))

  await screen.findByText(
    'The following dates already have meal plans. Overwrite them?'
  )
  expect(screen.getByText(startIso)).toBeInTheDocument()
  expect(mealPlansApi.generate).not.toHaveBeenCalled()

  await user.click(screen.getByRole('button', { name: /overwrite/i }))

  await waitFor(() => {
    expect(mealPlansApi.deleteRange).toHaveBeenCalledWith(startIso, endIso)
  })
  await waitFor(() => {
    expect(mealPlansApi.generate).toHaveBeenCalledTimes(1)
  })
  expect(mealPlansApi.create).toHaveBeenCalledTimes(1)
})
