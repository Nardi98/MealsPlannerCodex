/**
 * @vitest-environment jsdom
 */
import React from 'react'
import { render, screen, cleanup, waitFor, fireEvent } from '@testing-library/react'
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
    checkRange: vi.fn(),
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
  mealPlansApi.generate.mockResolvedValue({})
  mealPlansApi.create.mockResolvedValue()
  mealPlansApi.checkRange.mockResolvedValue([])
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

test('shows overwrite confirmation modal when conflicts are detected', async () => {
  mealPlansApi.checkRange.mockResolvedValue([
    { plan_date: '2024-01-01', meals: [] },
  ])

  render(<MealPlanPage />)

  await screen.findByText('Bulk')
  fireEvent.click(screen.getByRole('button', { name: /generate plan/i }))

  const modalHeading = await screen.findByText('Overwrite Existing Data')
  expect(modalHeading).toBeInTheDocument()
  expect(modalHeading.closest('div.fixed')).toMatchInlineSnapshot(`
    <div
      class="fixed inset-0 bg-black/60 flex items-center justify-center z-[70]"
    >
      <div
        class="rounded-2xl border bg-white p-4 shadow-sm space-y-4 w-full max-w-md"
        style="border-color: var(--border);"
      >
        <h3
          class="text-lg font-medium"
        >
          Overwrite Existing Data
        </h3>
        <p
          class="text-sm"
        >
          This will overwrite existing data. Are you sure?
        </p>
        <div
          class="flex justify-end gap-2 pt-2"
        >
          <button
            class="inline-flex items-center gap-2 rounded-2xl shadow-sm hover:opacity-95 border px-3 py-2 text-sm "
            style="background-color: transparent; color: var(--text-strong); border-color: var(--border);"
            type="button"
          >
            Cancel
          </button>
          <button
            class="inline-flex items-center gap-2 rounded-2xl shadow-sm hover:opacity-95 border px-3 py-2 text-sm "
            style="background-color: var(--c-neg); color: rgb(255, 255, 255); border-color: transparent;"
            type="button"
          >
            Overwrite
          </button>
        </div>
      </div>
    </div>
  `)
})

test('does not generate a plan when overwrite is cancelled', async () => {
  mealPlansApi.checkRange.mockResolvedValue([
    { plan_date: '2024-01-01', meals: [] },
  ])

  render(<MealPlanPage />)

  await screen.findByText('Bulk')
  fireEvent.click(screen.getByRole('button', { name: /generate plan/i }))

  const cancelButton = await screen.findByRole('button', { name: /cancel/i })
  fireEvent.click(cancelButton)

  await waitFor(() => {
    expect(screen.queryByText('Overwrite Existing Data')).not.toBeInTheDocument()
  })
  expect(mealPlansApi.deleteRange).not.toHaveBeenCalled()
  expect(mealPlansApi.generate).not.toHaveBeenCalled()
})

test('deletes existing plans before generating a new one on confirm', async () => {
  mealPlansApi.checkRange.mockResolvedValue([
    { plan_date: '2024-01-01', meals: [] },
  ])

  render(<MealPlanPage />)

  await screen.findByText('Bulk')
  fireEvent.click(screen.getByRole('button', { name: /generate plan/i }))

  const confirmButton = await screen.findByRole('button', { name: /overwrite/i })
  fireEvent.click(confirmButton)

  await waitFor(() => {
    expect(mealPlansApi.deleteRange).toHaveBeenCalledTimes(1)
    expect(mealPlansApi.generate).toHaveBeenCalledTimes(1)
  })

  expect(
    mealPlansApi.deleteRange.mock.invocationCallOrder[0]
  ).toBeLessThan(mealPlansApi.generate.mock.invocationCallOrder[0])
})
