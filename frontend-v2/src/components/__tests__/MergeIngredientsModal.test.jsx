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

const PAIR = {
  a: { id: 1, name: 'Tomato', unit: 'g', recipe_count: 2 },
  b: { id: 2, name: 'Tomatoes', unit: 'piece', recipe_count: 1 },
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
  const pairButton = await screen.findByText(/Tomato \(g\)/)
  fireEvent.click(pairButton)
  await screen.findByText('Surviving unit')
}

test('unit mismatch reveals conversion-factor input', async () => {
  await openPair()
  // survivor default = A (Tomato, g); source = B (Tomatoes, piece) => units differ
  expect(screen.getByLabelText('Conversion factor')).toBeInTheDocument()
})

test('leave as-is sends conversion_factor null', async () => {
  await openPair()
  fireEvent.click(screen.getByLabelText(/Leave source units as-is/))
  fireEvent.click(screen.getByRole('button', { name: 'Merge' }))
  await waitFor(() => expect(ingredientsApi.merge).toHaveBeenCalled())
  expect(ingredientsApi.merge).toHaveBeenCalledWith(
    expect.objectContaining({
      source_id: 2,
      target_id: 1,
      conversion_factor: null,
    })
  )
})

test('confirm calls merge with correct source/target and factor', async () => {
  await openPair()
  fireEvent.change(screen.getByLabelText('Conversion factor'), {
    target: { value: '150' },
  })
  fireEvent.click(screen.getByRole('button', { name: 'Merge' }))
  await waitFor(() => expect(ingredientsApi.merge).toHaveBeenCalled())
  expect(ingredientsApi.merge).toHaveBeenCalledWith(
    expect.objectContaining({
      source_id: 2,
      target_id: 1,
      surviving_unit: 'g',
      conversion_factor: 150,
    })
  )
})
