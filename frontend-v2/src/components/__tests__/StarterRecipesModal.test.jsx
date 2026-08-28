/**
 * @vitest-environment jsdom
 */
import React from 'react'
import { render, screen, fireEvent, waitFor, cleanup, within } from '@testing-library/react'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import '@testing-library/jest-dom/vitest'
import StarterRecipesModal from '../StarterRecipesModal'
import { STARTER_RECIPES, groupStarterRecipes } from '../../constants/starterRecipes'
import { recipesApi } from '../../api/recipesApi'

vi.mock('../../api/recipesApi', () => ({
  recipesApi: { create: vi.fn(() => Promise.resolve({ id: 1 })) },
}))

// The account's own ingredient rows, as /ingredients returns them.
const OWNED = [
  { id: 7, name: 'Cherry Tomato', unit: 'g', season_months: [6, 7, 8, 9] },
  { id: 8, name: 'Pasta', unit: 'g', season_months: [] },
]

beforeEach(() => {
  vi.clearAllMocks()
  recipesApi.create.mockResolvedValue({ id: 1 })
})

afterEach(cleanup)

function renderModal(props = {}) {
  return render(
    <StarterRecipesModal
      onClose={props.onClose || vi.fn()}
      onImported={props.onImported || vi.fn()}
      ingredients={OWNED}
    />,
  )
}

// Every test waits on the same first row, so the wait lives in the helper.
async function renderAndWait(props) {
  renderModal(props)
  await screen.findByRole('heading', { level: 4, name: 'First courses' })
}

const addButton = () => screen.getByRole('button', { name: /^Add \d+ recipes?$/ })

test('renders every recipe, grouped by course', async () => {
  await renderAndWait()

  const headings = screen.getAllByRole('heading', { level: 4 }).map((h) => h.textContent)
  expect(headings).toEqual(['First courses', 'Mains', 'Sides'])
  expect(screen.getAllByRole('checkbox')).toHaveLength(STARTER_RECIPES.length + headings.length)
})

test('every recipe starts selected', async () => {
  await renderAndWait()
  expect(addButton()).toHaveTextContent(`Add ${STARTER_RECIPES.length} recipes`)
  expect(screen.getByLabelText('Pasta alla Norma')).toBeChecked()
})

test('deselect all empties the selection and disables the add button', async () => {
  await renderAndWait()

  fireEvent.click(screen.getByRole('button', { name: 'Deselect all' }))

  expect(screen.getByLabelText('Pasta alla Norma')).not.toBeChecked()
  expect(addButton()).toBeDisabled()

  fireEvent.click(screen.getByRole('button', { name: 'Select all' }))
  expect(addButton()).toHaveTextContent(`Add ${STARTER_RECIPES.length} recipes`)
})

test('a section checkbox toggles only that section', async () => {
  await renderAndWait()

  const firstCount = groupStarterRecipes(STARTER_RECIPES)
    .find((g) => g.key === 'first-course').recipes.length
  fireEvent.click(screen.getByLabelText('First courses', { selector: 'input' }))

  expect(screen.getByLabelText('Pasta alla Norma')).not.toBeChecked()
  expect(screen.getByLabelText('Shakshuka')).toBeChecked()
  expect(addButton()).toHaveTextContent(`Add ${STARTER_RECIPES.length - firstCount} recipes`)
})

test('importing creates only the ticked recipes and reuses the owned ingredients', async () => {
  const onImported = vi.fn()
  await renderAndWait({ onImported })

  fireEvent.click(screen.getByRole('button', { name: 'Deselect all' }))
  fireEvent.click(screen.getByLabelText('Tuna and Cherry Tomato Pasta'))
  fireEvent.click(addButton())

  await waitFor(() => expect(onImported).toHaveBeenCalledTimes(1))
  expect(recipesApi.create).toHaveBeenCalledTimes(1)

  const payload = recipesApi.create.mock.calls[0][0]
  expect(payload.title).toBe('Tuna and Cherry Tomato Pasta')
  expect(payload.course).toBe('first-course')
  expect(payload.tags).toEqual(['pasta', 'quick', 'cheap'])
  // The pack's quantities go in as authored, so their basis goes with them --
  // one person here, since this entry states no other.
  expect(payload.servings).toBe(1)

  // Matched against the account's own row, so the import reuses it rather than
  // creating a near-duplicate ingredient.
  const tomato = payload.ingredients.find((i) => i.name === 'Cherry Tomato')
  expect(tomato.id).toBe(7)
  expect(tomato.unit).toBe('g')
  expect(tomato.amount).toBe(120)

  // An ingredient the account somehow lacks is still sent, by name only.
  const parsley = payload.ingredients.find((i) => i.name === 'Parsley')
  expect(parsley.id).toBeUndefined()
})

test('a failed creation keeps the modal open and reports what failed', async () => {
  const onImported = vi.fn()
  recipesApi.create.mockRejectedValueOnce(new Error('boom'))
  await renderAndWait({ onImported })

  fireEvent.click(screen.getByRole('button', { name: 'Deselect all' }))
  fireEvent.click(screen.getByLabelText('Shakshuka'))
  fireEvent.click(addButton())

  const alert = await screen.findByRole('alert')
  expect(within(alert).getByText(/Shakshuka/)).toBeInTheDocument()
  expect(onImported).not.toHaveBeenCalled()
  expect(screen.getByLabelText('Shakshuka')).toBeChecked()
})

test('Maybe later closes without creating anything', async () => {
  const onClose = vi.fn()
  await renderAndWait({ onClose })

  fireEvent.click(screen.getByRole('button', { name: 'Maybe later' }))

  expect(onClose).toHaveBeenCalledTimes(1)
  expect(recipesApi.create).not.toHaveBeenCalled()
})
