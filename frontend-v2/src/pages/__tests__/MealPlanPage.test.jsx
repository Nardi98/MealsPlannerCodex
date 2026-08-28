/**
 * @vitest-environment jsdom
 */
import React from 'react'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, afterEach, expect, test, vi } from 'vitest'
import '@testing-library/jest-dom/vitest'
import MealPlanPage from '../MealPlanPage'
import { stubViewport } from '../../test/stubViewport'
import { mealPlansApi } from '../../api/mealPlansApi'
import { tagsApi } from '../../api/tagsApi'
import { feedbackApi } from '../../api/feedbackApi'
import { recipesApi } from '../../api/recipesApi'

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

test('rejecting a leftover meal clears leftover flag for replacement', async () => {
  const user = userEvent.setup()
  const today = new Date()
  const day = today.getDay()
  const diff = day === 0 ? -6 : 1 - day
  const start = new Date(today)
  start.setDate(today.getDate() + diff)
  const startIso = start.toISOString().slice(0, 10)

  mealPlansApi.create.mockResolvedValue()
  feedbackApi.rejectRecipe.mockResolvedValue('Replacement')
  recipesApi.fetchAll.mockResolvedValue([
    { id: 1, title: 'Bulk' },
    { id: 2, title: 'Replacement' },
  ])
  // Mount fetch returns the leftover; the post-reject refetch returns the replacement.
  mealPlansApi.fetchRange
    .mockResolvedValueOnce({
      [startIso]: [{ recipe: 'Bulk', side_recipes: [], accepted: false, leftover: true }],
    })
    .mockResolvedValueOnce({
      [startIso]: [
        { recipe: 'Replacement', side_recipes: [], accepted: false, leftover: false },
      ],
    })

  render(<MealPlanPage />)

  await screen.findByText('Bulk')
  await user.click(screen.getByText('Bulk'))
  // The calendar cell now has its own labelled "Reject Bulk" control, so match
  // the modal's button exactly rather than by substring.
  await user.click(await screen.findByRole('button', { name: 'Reject' }))

  await waitFor(() => {
    expect(mealPlansApi.create).toHaveBeenCalledWith({
      plan_date: startIso,
      plan: {
        [startIso]: [
          {
            main_id: 2,
            side_ids: [],
            leftover: false,
            meal_number: 1,
          },
        ],
      },
    })
  })

  expect(screen.queryByAltText('Leftover')).not.toBeInTheDocument()
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

test('on mobile the plan settings sit below the calendar, collapsed', async () => {
  stubViewport(true)
  const { container } = render(<MealPlanPage />)
  await screen.findByText('Meal Plan')

  const toggle = screen.getByRole('button', { name: /plan settings/i })
  const calendar = container.querySelector('[data-tour="mealplan-calendar"]')

  // Collapsed by default: the calendar is what the page is for.
  expect(toggle).toHaveAttribute('aria-expanded', 'false')
  expect(container.querySelector('[data-tour="mealplan-tabs"]')).toBeNull()

  // The settings used to be pulled above the calendar with CSS `order`, which
  // put a control panel between the heading and the plan itself. Visual order
  // now follows the DOM at every width, so tab order agrees with the page.
  const sections = [...container.querySelectorAll('[data-plan-section]')]
  sections.forEach((section) => {
    expect(section.className).not.toContain('order-')
  })
  expect(sections.indexOf(calendar.closest('[data-plan-section]'))).toBeLessThan(
    sections.indexOf(toggle.closest('[data-plan-section]')),
  )
})

test('on desktop the settings render below the calendar, always open', async () => {
  stubViewport(false)
  const { container } = render(<MealPlanPage />)
  await screen.findByText('Meal Plan')

  expect(screen.queryByRole('button', { name: /plan settings/i })).not.toBeInTheDocument()
  expect(container.querySelector('[data-tour="mealplan-tabs"]')).not.toBeNull()
})
