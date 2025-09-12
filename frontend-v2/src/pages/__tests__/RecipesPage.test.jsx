/**
 * @vitest-environment jsdom
 */
import React from 'react'
import {
  render,
  screen,
  fireEvent,
  waitFor,
  cleanup,
} from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import '@testing-library/jest-dom/vitest'
import RecipesPage from '../RecipesPage'
import { recipesApi } from '../../api/recipesApi'
import { tagsApi } from '../../api/tagsApi'
import { ingredientsApi } from '../../api/ingredientsApi'

vi.mock('../../api/recipesApi', () => ({
  recipesApi: {
    fetchAll: vi.fn(),
  },
}))

vi.mock('../../api/tagsApi', () => ({
  tagsApi: {
    fetchAll: vi.fn(),
  },
}))

vi.mock('../../api/ingredientsApi', () => ({
  ingredientsApi: {
    fetchAll: vi.fn(),
  },
}))

afterEach(() => {
  vi.restoreAllMocks()
  cleanup()
})

test('filters recipes as user types', async () => {
  recipesApi.fetchAll.mockResolvedValue([
    { id: 1, title: 'Spaghetti', course: 'main' },
    { id: 2, title: 'Pizza', course: 'main' },
  ])
  tagsApi.fetchAll.mockResolvedValue([])
  ingredientsApi.fetchAll.mockResolvedValue([])

  render(<RecipesPage />)

  // Wait for recipes to load
  await screen.findByText('Spaghetti')
  await screen.findByText('Pizza')

  const input = screen.getByPlaceholderText('Search recipes…')
  fireEvent.change(input, { target: { value: 'spa' } })

  await waitFor(() => {
    expect(screen.getByText('Spaghetti')).toBeInTheDocument()
    expect(screen.queryByText('Pizza')).toBeNull()
  })

  fireEvent.change(input, { target: { value: '' } })

  await waitFor(() => {
    expect(screen.getByText('Pizza')).toBeInTheDocument()
  })
})

test('filters recipes by tags and ingredients', async () => {
  recipesApi.fetchAll.mockResolvedValue([
    {
      id: 1,
      title: 'Spaghetti',
      tags: ['Italian'],
      ingredients: [{ name: 'Tomato' }, { name: 'Salt' }],
      course: 'main',
    },
    {
      id: 2,
      title: 'Salad',
      tags: ['Vegan'],
      ingredients: [{ name: 'Lettuce' }, { name: 'Tomato' }],
      course: 'side',
    },
  ])
  tagsApi.fetchAll.mockResolvedValue([{ name: 'Italian' }, { name: 'Vegan' }])
  ingredientsApi.fetchAll.mockResolvedValue([
    { id: 1, name: 'Tomato' },
    { id: 2, name: 'Lettuce' },
    { id: 3, name: 'Salt' },
  ])

  render(<RecipesPage />)

  await screen.findByText('Spaghetti')
  await screen.findByText('Salad')

  fireEvent.click(screen.getByLabelText('Filter'))
  fireEvent.click(screen.getByText('Tags'))
  fireEvent.click(screen.getByLabelText('Italian'))

  await waitFor(() => {
    expect(screen.getByText('Spaghetti')).toBeInTheDocument()
    expect(screen.queryByText('Salad')).toBeNull()
  })

  fireEvent.click(screen.getByLabelText('Italian'))
  fireEvent.click(screen.getByText('Ingredients'))
  fireEvent.click(screen.getByLabelText('Lettuce'))

  await waitFor(() => {
    expect(screen.getByText('Salad')).toBeInTheDocument()
    expect(screen.queryByText('Spaghetti')).toBeNull()
  })
})

test('filters recipes by course', async () => {
  recipesApi.fetchAll.mockResolvedValue([
    { id: 1, title: 'Soup', course: 'main' },
    { id: 2, title: 'Cake', course: 'dessert' },
  ])
  tagsApi.fetchAll.mockResolvedValue([])
  ingredientsApi.fetchAll.mockResolvedValue([])

  render(<RecipesPage />)

  await screen.findByText('Soup')
  await screen.findByText('Cake')

  fireEvent.click(screen.getByLabelText('Filter'))
  fireEvent.click(screen.getByText('Course'))
  fireEvent.click(screen.getByLabelText('dessert'))

  await waitFor(() => {
    expect(screen.getByText('Cake')).toBeInTheDocument()
    expect(screen.queryByText('Soup')).toBeNull()
  })
})
