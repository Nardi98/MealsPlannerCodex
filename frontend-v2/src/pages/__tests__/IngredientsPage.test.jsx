/**
 * @vitest-environment jsdom
 */
import React from 'react'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import { beforeEach, afterEach, expect, test, vi } from 'vitest'
import '@testing-library/jest-dom/vitest'
import IngredientsPage from '../IngredientsPage'
import { ingredientsApi } from '../../api/ingredientsApi'

vi.mock('../../api/ingredientsApi', () => ({
  ingredientsApi: {
    fetchAll: vi.fn(),
    search: vi.fn(),
    recipes: vi.fn(),
  },
}))

const INGREDIENTS = [
  { id: 1, name: 'Tomato', unit: 'g', season_months: [], categories: ['Vegetables'] },
  { id: 2, name: 'Salmon', unit: 'g', season_months: [], categories: ['Fish'] },
]

beforeEach(() => {
  localStorage.clear()
  ingredientsApi.fetchAll.mockResolvedValue(INGREDIENTS)
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

test('deselecting a pill hides its section', async () => {
  render(<IngredientsPage />)
  await screen.findByText('Tomato')
  expect(screen.getByText('Salmon')).toBeInTheDocument()

  // Click the Fish pill to deselect it.
  const fishPill = screen.getByRole('button', { name: 'Fish filter' })
  fireEvent.click(fishPill)

  await waitFor(() => expect(screen.queryByText('Salmon')).not.toBeInTheDocument())
  // Tomato (Vegetables) still visible.
  expect(screen.getByText('Tomato')).toBeInTheDocument()
})

test('collapse state persists to localStorage', async () => {
  render(<IngredientsPage />)
  await screen.findByText('Tomato')

  const header = screen.getByRole('button', { name: 'Vegetables section' })
  fireEvent.click(header)

  await waitFor(() => {
    const stored = JSON.parse(localStorage.getItem('ingredientSectionCollapsed'))
    expect(stored.Vegetables).toBe(true)
  })
})
