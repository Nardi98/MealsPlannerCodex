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
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import '@testing-library/jest-dom/vitest'
import RecipesPage from '../RecipesPage'
import { recipesApi } from '../../api/recipesApi'
import { tagsApi } from '../../api/tagsApi'
import { ingredientsApi } from '../../api/ingredientsApi'

vi.mock('../../api/recipesApi', () => ({
  recipesApi: {
    fetchAll: vi.fn(),
    update: vi.fn(),
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

beforeEach(() => {
  // The dish-glyph Icon fetches SVGs from a CDN; keep tests hermetic.
  globalThis.fetch = vi.fn(() => Promise.reject(new Error('no network')))
})

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

test('clicking a card opens a detail modal with ingredients and procedure', async () => {
  recipesApi.fetchAll.mockResolvedValue([
    {
      id: 1,
      title: 'Risotto',
      course: 'main',
      tags: [],
      ingredients: [{ name: 'Rice', amount: 200, unit: 'g' }],
      procedure: 'Stir slowly.',
    },
  ])
  tagsApi.fetchAll.mockResolvedValue([])
  ingredientsApi.fetchAll.mockResolvedValue([])

  render(<RecipesPage />)
  fireEvent.click(await screen.findByText('Risotto'))

  await screen.findByText('Procedure')
  expect(screen.getByText('Stir slowly.')).toBeInTheDocument()
  expect(screen.getByText(/Rice/)).toBeInTheDocument()
})

test('renders the recipe image when image_url is present', async () => {
  recipesApi.fetchAll.mockResolvedValue([
    { id: 1, title: 'Tacos', course: 'main', image_url: 'https://x/y.jpg', ingredients: [] },
  ])
  tagsApi.fetchAll.mockResolvedValue([])
  ingredientsApi.fetchAll.mockResolvedValue([])

  render(<RecipesPage />)
  await screen.findByText('Tacos')
  const img = screen.getByAltText('Tacos photo')
  expect(img).toHaveAttribute('src', 'https://x/y.jpg')
})

test('shows a placeholder (no photo) when image_url is absent', async () => {
  recipesApi.fetchAll.mockResolvedValue([
    { id: 1, title: 'Tacos', course: 'main', ingredients: [] },
  ])
  tagsApi.fetchAll.mockResolvedValue([])
  ingredientsApi.fetchAll.mockResolvedValue([])

  render(<RecipesPage />)
  await screen.findByText('Tacos')
  expect(screen.queryByAltText('Tacos photo')).toBeNull()
})

// --- Favorite sides, curated from the detail modal -------------------------

const ROAST = {
  id: 1,
  title: 'Roast Chicken',
  course: 'main',
  tags: [],
  ingredients: [],
  procedure: 'Roast it.',
  favorite_side_ids: [],
}
const POTATOES = {
  id: 2, title: 'Mashed Potatoes', course: 'side', tags: [], ingredients: [],
}
const BROCCOLI = {
  id: 3, title: 'Steamed Broccoli', course: 'side', tags: [], ingredients: [],
}

const openDetail = async (recipes, title = 'Roast Chicken') => {
  recipesApi.fetchAll.mockResolvedValue(recipes)
  tagsApi.fetchAll.mockResolvedValue([])
  ingredientsApi.fetchAll.mockResolvedValue([])
  render(<RecipesPage />)
  fireEvent.click(await screen.findByText(title))
  return screen.findByText('Procedure')
}

test('the detail modal offers favorite sides under the procedure', async () => {
  await openDetail([ROAST, POTATOES, BROCCOLI])

  expect(screen.getByText('Favorite sides')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: /add a side/i }))
  expect(screen.getByRole('option', { name: 'Mashed Potatoes' })).toBeInTheDocument()
  // Only sides are offered.
  expect(screen.queryByRole('option', { name: 'Roast Chicken' })).toBeNull()
})

test('a side dish is not offered favorite sides of its own', async () => {
  await openDetail([{ ...POTATOES, procedure: 'Mash.' }], 'Mashed Potatoes')

  expect(screen.queryByText('Favorite sides')).toBeNull()
})

test('a first course is not offered favorite sides', async () => {
  // Favorite sides are a main-dish feature only.
  await openDetail(
    [
      {
        id: 4, title: 'Risotto', course: 'first-course',
        tags: [], ingredients: [], procedure: 'Stir.',
      },
      POTATOES,
    ],
    'Risotto'
  )

  expect(screen.queryByText('Favorite sides')).toBeNull()
})

test('picking a side saves it immediately without an explicit save', async () => {
  recipesApi.update.mockImplementation((id, recipe) =>
    Promise.resolve({ ...ROAST, ...recipe, id })
  )
  await openDetail([ROAST, POTATOES, BROCCOLI])

  fireEvent.click(screen.getByRole('button', { name: /add a side/i }))
  fireEvent.click(screen.getByRole('option', { name: 'Steamed Broccoli' }))

  await waitFor(() => expect(recipesApi.update).toHaveBeenCalledTimes(1))
  const [id, payload] = recipesApi.update.mock.calls[0]
  expect(id).toBe(1)
  expect(payload.favorite_side_ids).toEqual([3])
  // The rest of the recipe must ride along, or serialiseRecipe wipes it.
  expect(payload).toMatchObject({ title: 'Roast Chicken', procedure: 'Roast it.' })
  expect(await screen.findByTestId('favorite-side-chip-3')).toBeInTheDocument()
})

test('removing a side saves the shortened list', async () => {
  recipesApi.update.mockImplementation((id, recipe) =>
    Promise.resolve({ ...ROAST, ...recipe, id })
  )
  await openDetail([{ ...ROAST, favorite_side_ids: [2, 3] }, POTATOES, BROCCOLI])

  fireEvent.click(screen.getByRole('button', { name: /remove mashed potatoes/i }))

  await waitFor(() => expect(recipesApi.update).toHaveBeenCalledTimes(1))
  expect(recipesApi.update.mock.calls[0][1].favorite_side_ids).toEqual([3])
})

test('a failed save reverts the picker instead of lying', async () => {
  recipesApi.update.mockRejectedValue(new Error('boom'))
  vi.spyOn(console, 'error').mockImplementation(() => {})
  await openDetail([ROAST, POTATOES, BROCCOLI])

  fireEvent.click(screen.getByRole('button', { name: /add a side/i }))
  fireEvent.click(screen.getByRole('option', { name: 'Steamed Broccoli' }))

  await waitFor(() => expect(recipesApi.update).toHaveBeenCalled())
  await waitFor(() =>
    expect(screen.queryByTestId('favorite-side-chip-3')).toBeNull()
  )
})

test('deletes a recipe from the detail modal', async () => {
  recipesApi.fetchAll.mockResolvedValue([
    { id: 1, title: 'Risotto', course: 'main', tags: [], ingredients: [], procedure: '' },
  ])
  tagsApi.fetchAll.mockResolvedValue([])
  ingredientsApi.fetchAll.mockResolvedValue([])
  recipesApi.delete = vi.fn().mockResolvedValue(null)

  render(<RecipesPage />)
  fireEvent.click(await screen.findByText('Risotto'))
  fireEvent.click(await screen.findByText('Delete'))

  await waitFor(() => expect(screen.queryByText('Risotto')).toBeNull())
  expect(recipesApi.delete).toHaveBeenCalledWith(1)
})
