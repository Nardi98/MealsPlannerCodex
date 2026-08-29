/**
 * @vitest-environment jsdom
 */
import React from 'react'
import { render, screen, fireEvent, cleanup } from '@testing-library/react'
import { beforeEach, afterEach, expect, test, vi } from 'vitest'
import '@testing-library/jest-dom/vitest'
import ShoppingListPage from '../ShoppingListPage'
import { mealPlansApi } from '../../api/mealPlansApi'
import { recipesApi } from '../../api/recipesApi'
import { authApi } from '../../api/authApi'
import { stubViewport } from '../../test/stubViewport'

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

// --- mobile layout ----------------------------------------------------------

test('shows a single month on mobile', async () => {
  stubViewport(true)
  render(<ShoppingListPage />)
  await screen.findByText('ing1: 2 kg')

  expect(screen.getAllByTestId('shopping-month')).toHaveLength(1)
})

test('keeps three months on desktop', async () => {
  stubViewport(false)
  render(<ShoppingListPage />)
  await screen.findByText('A')

  expect(screen.getAllByTestId('shopping-month')).toHaveLength(3)
})

test('mobile opens on the ingredients tab and hides the meal list', async () => {
  stubViewport(true)
  render(<ShoppingListPage />)

  expect(await screen.findByText('ing1: 2 kg')).toBeInTheDocument()
  // 'A' is a meal title, which lives on the other tab.
  expect(screen.queryByText('A')).toBeNull()
})

test('mobile can switch to the meal list', async () => {
  stubViewport(true)
  render(<ShoppingListPage />)
  await screen.findByText('ing1: 2 kg')

  fireEvent.click(screen.getByRole('button', { name: 'Meals' }))

  expect(await screen.findByText('A')).toBeInTheDocument()
  expect(screen.queryByText('ing1: 2 kg')).toBeNull()
})

test('desktop shows both lists at once and no tabs', async () => {
  stubViewport(false)
  render(<ShoppingListPage />)

  expect(await screen.findByText('A')).toBeInTheDocument()
  expect(screen.getByText('ing1: 2 kg')).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Meals' })).toBeNull()
})

test('the batch label flows inline with the recipe title', async () => {
  const todayIso = new Date().toISOString().slice(0, 10)
  mealPlansApi.fetchRange.mockResolvedValue({
    [todayIso]: [
      { recipe: 'A', side_recipes: [], leftover: false, meal_number: 1, people: 2 },
    ],
  })
  recipesApi.fetchAll.mockResolvedValue([
    { id: 1, title: 'A', servings: 4, ingredients: [] },
  ])

  render(<ShoppingListPage />)

  const label = await screen.findByText('×½')
  // Same text flow as the title, not a separate flex item beside it. The gap
  // is a margin rather than a space, which is deliberate: with no break
  // opportunity between them the label stays bound to the last word instead
  // of stranding on a line of its own again.
  expect(label.parentElement).toHaveTextContent('A×½')
  expect(label.parentElement.className).not.toMatch(/flex/)
})

// --- ticking off ------------------------------------------------------------

test('an ingredient row is a button that toggles pressed', async () => {
  render(<ShoppingListPage />)
  const row = await screen.findByRole('button', { name: /ing1: 2 kg/ })

  expect(row).toHaveAttribute('aria-pressed', 'false')

  fireEvent.click(row)

  expect(screen.getByRole('button', { name: /ing1: 2 kg/ })).toHaveAttribute(
    'aria-pressed',
    'true',
  )
})

test('a ticked ingredient unticks when its quantity changes', async () => {
  render(<ShoppingListPage />)
  fireEvent.click(await screen.findByRole('button', { name: /ing1: 2 kg/ }))
  expect(screen.getByRole('button', { name: /ing1: 2 kg/ })).toHaveAttribute(
    'aria-pressed',
    'true',
  )

  // Meal A goes from 2 people to 3, so ing1 becomes 3 kg.
  fireEvent.click(screen.getAllByRole('button', { name: 'More people' })[0])

  const row = await screen.findByRole('button', { name: /ing1: 3 kg/ })
  expect(row).toHaveAttribute('aria-pressed', 'false')
})

test('a quantity change leaves other ticks alone', async () => {
  render(<ShoppingListPage />)
  fireEvent.click(await screen.findByRole('button', { name: /ing2: 3 kg/ }))

  fireEvent.click(screen.getAllByRole('button', { name: 'More people' })[0])

  expect(
    await screen.findByRole('button', { name: /ing2: 3 kg/ }),
  ).toHaveAttribute('aria-pressed', 'true')
})

test('ticked items are left out of the export', async () => {
  // jsdom implements neither of these, so assign them rather than spying.
  URL.createObjectURL = vi.fn(() => 'blob:x')
  URL.revokeObjectURL = vi.fn()
  const blobSpy = vi.spyOn(globalThis, 'Blob')

  render(<ShoppingListPage />)
  fireEvent.click(await screen.findByRole('button', { name: /ing1: 2 kg/ }))
  fireEvent.click(screen.getByRole('button', { name: 'Export open items' }))

  const text = blobSpy.mock.calls[0][0][0]
  expect(text).not.toMatch(/ing1/)
  expect(text).toMatch(/ing2/)
})
