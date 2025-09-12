/**
 * @vitest-environment jsdom
 */
import React from 'react'
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import '@testing-library/jest-dom/vitest'
import RecipesPage from '../RecipesPage'
import { recipesApi } from '../../api/recipesApi'

vi.mock('../../api/recipesApi', () => ({
  recipesApi: {
    fetchAll: vi.fn(),
    update: vi.fn(),
    create: vi.fn(),
    delete: vi.fn(),
  },
}))

afterEach(() => {
  vi.restoreAllMocks()
  cleanup()
})

test('filters recipes by course', async () => {
  recipesApi.fetchAll.mockResolvedValue([
    { id: 1, title: 'Salad', course: 'first-course', ingredients: [], score: 0 },
    { id: 2, title: 'Steak', course: 'main', ingredients: [], score: 0 },
    { id: 3, title: 'Fries', course: 'side', ingredients: [], score: 0 },
  ])

  render(<RecipesPage />)

  await waitFor(() => expect(recipesApi.fetchAll).toHaveBeenCalled())
  expect(screen.getByText('Salad')).toBeInTheDocument()
  expect(screen.getByText('Steak')).toBeInTheDocument()
  expect(screen.getByText('Fries')).toBeInTheDocument()

  const select = screen.getByRole('combobox')
  fireEvent.change(select, { target: { value: 'main' } })

  expect(screen.queryByText('Salad')).not.toBeInTheDocument()
  expect(screen.getByText('Steak')).toBeInTheDocument()
  expect(screen.queryByText('Fries')).not.toBeInTheDocument()
})
