/**
 * @vitest-environment jsdom
 */
import React from 'react'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import { beforeEach, afterEach, expect, test, vi } from 'vitest'
import '@testing-library/jest-dom/vitest'
import MergeIngredientsModal from '../MergeIngredientsModal'
import { ingredientsApi } from '../../api/ingredientsApi'

vi.mock('../../api/ingredientsApi', () => ({
  ingredientsApi: {
    duplicates: vi.fn(),
    recipes: vi.fn(),
    merge: vi.fn(),
  },
}))

// Tomato is weighed and Tomatoes are counted. That used to demand a
// hand-supplied bridge; the survivor's own conversions supply it now.
const PAIR = {
  a: { id: 1, name: 'Tomato', grams_per_piece: 120, recipe_count: 2 },
  b: { id: 2, name: 'Tomatoes', grams_per_piece: null, recipe_count: 1 },
  score: 0.9,
}

beforeEach(() => {
  ingredientsApi.duplicates.mockResolvedValue([PAIR])
  ingredientsApi.recipes.mockResolvedValue([{ id: 10, title: 'Salad' }])
  ingredientsApi.merge.mockResolvedValue({})
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

async function openPair() {
  render(<MergeIngredientsModal onClose={() => {}} onMerged={() => {}} />)
  fireEvent.click(await screen.findByRole('button', { name: /Tomato.*Tomatoes/ }))
  await screen.findByText(/Keep \(survivor\)/)
}

test('the merge asks only which ingredient survives', async () => {
  await openPair()

  fireEvent.click(screen.getByRole('button', { name: 'Merge' }))

  await waitFor(() => expect(ingredientsApi.merge).toHaveBeenCalled())
  expect(ingredientsApi.merge).toHaveBeenCalledWith({
    source_id: 2,
    target_id: 1,
  })
})

test('no unit or conversion is asked for any more', async () => {
  await openPair()

  expect(screen.queryByLabelText('Surviving unit')).toBeNull()
  expect(screen.queryByLabelText('Conversion factor')).toBeNull()
  expect(screen.queryByLabelText(/Leave source units as-is/)).toBeNull()
})

test('flipping the survivor flips which one is merged away', async () => {
  await openPair()

  fireEvent.click(screen.getByRole('radio', { name: /Tomatoes/ }))
  fireEvent.click(screen.getByRole('button', { name: 'Merge' }))

  await waitFor(() => expect(ingredientsApi.merge).toHaveBeenCalled())
  expect(ingredientsApi.merge).toHaveBeenCalledWith({
    source_id: 1,
    target_id: 2,
  })
})

test('the recipes a merge will touch are named before it happens', async () => {
  await openPair()
  expect(await screen.findByText('Salad')).toBeInTheDocument()
})

test('a refused merge shows the reason the server gave', async () => {
  // The backend refuses a merge it cannot carry out and says why: which
  // recipe blocks it, and which conversion factor is missing. `request()`
  // unwraps FastAPI's {detail} into the Error message, and that sentence is
  // the whole point -- a generic "failed" tells the user nothing about the
  // factor they need to go and fill in.
  const detail =
    'Cannot merge: recipe "Salad" measures Tomatoes by volume and ' +
    'Tomato has no grams_per_ml'
  ingredientsApi.merge.mockRejectedValue(new Error(detail))

  await openPair()
  fireEvent.click(screen.getByRole('button', { name: 'Merge' }))

  expect(await screen.findByText(detail)).toBeInTheDocument()
})
