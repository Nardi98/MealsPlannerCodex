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
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import RecipesPage from '../RecipesPage'
import { recipesApi } from '../../api/recipesApi'
import { tagsApi } from '../../api/tagsApi'
import { ingredientsApi } from '../../api/ingredientsApi'
import { stubViewport } from '../../test/stubViewport'

// Stands in for the tour so a test can read the gate RecipesPage passes it.
vi.mock('../../tutorial/PageTour', async () => {
  const { createElement } = await vi.importActual('react')
  return {
    PageTour: ({ id, enabled }) =>
      createElement('div', { 'data-testid': `page-tour-${id}`, 'data-enabled': String(enabled) }),
  }
})

// The empty-book call to action navigates, so the page needs a router; the
// /discover stub lets a test see where it went.
const renderPage = () =>
  render(
    <MemoryRouter initialEntries={['/recipes']}>
      <Routes>
        <Route path="/recipes" element={<RecipesPage />} />
        <Route path="/discover" element={<p>Discover page</p>} />
      </Routes>
    </MemoryRouter>
  )

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

  renderPage()

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

  renderPage()

  await screen.findByText('Spaghetti')
  await screen.findByText('Salad')

  fireEvent.click(screen.getByLabelText('Filter'))
  fireEvent.click(screen.getByRole('button', { name: 'Tags' }))
  fireEvent.click(screen.getByRole('button', { name: 'Italian' }))

  await waitFor(() => {
    expect(screen.getByText('Spaghetti')).toBeInTheDocument()
    expect(screen.queryByText('Salad')).toBeNull()
  })

  fireEvent.click(screen.getByRole('button', { name: 'Italian' }))
  fireEvent.click(screen.getByRole('button', { name: 'Ingredients' }))
  // The ingredient group lists nothing until it is searched.
  fireEvent.change(screen.getByPlaceholderText('Search Ingredients…'), {
    target: { value: 'lettuce' },
  })
  fireEvent.click(screen.getByRole('button', { name: 'Lettuce' }))

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

  renderPage()

  await screen.findByText('Soup')
  await screen.findByText('Cake')

  fireEvent.click(screen.getByLabelText('Filter'))
  fireEvent.click(screen.getByRole('button', { name: 'Course' }))
  fireEvent.click(screen.getByRole('button', { name: 'dessert' }))

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

  renderPage()
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

  renderPage()
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

  renderPage()
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
  renderPage()
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

  renderPage()
  fireEvent.click(await screen.findByText('Risotto'))
  fireEvent.click(await screen.findByRole('button', { name: 'Delete' }))
  // The delete is now guarded: the first click only asks.
  fireEvent.click(await screen.findByRole('button', { name: 'Delete recipe' }))

  await waitFor(() => expect(screen.queryByText('Risotto')).toBeNull())
  expect(recipesApi.delete).toHaveBeenCalledWith(1)
})

// SH-12: the share control must be reachable from the existing recipe modal.
test('opens the share dialog from the recipe detail modal', async () => {
  recipesApi.fetchAll.mockResolvedValue([
    { id: 1, title: 'Risotto', course: 'main', tags: [], ingredients: [], procedure: '' },
  ])
  tagsApi.fetchAll.mockResolvedValue([])
  ingredientsApi.fetchAll.mockResolvedValue([])

  renderPage()
  fireEvent.click(await screen.findByText('Risotto'))
  fireEvent.click(await screen.findByRole('button', { name: /^share$/i }))

  expect(
    await screen.findByText(/Anyone with the link can open this recipe/i)
  ).toBeInTheDocument()
})

// Reopening a recipe must not resurrect the previous share dialog.
test('closing the detail modal also drops the share dialog', async () => {
  recipesApi.fetchAll.mockResolvedValue([
    { id: 1, title: 'Risotto', course: 'main', tags: [], ingredients: [], procedure: '' },
  ])
  tagsApi.fetchAll.mockResolvedValue([])
  ingredientsApi.fetchAll.mockResolvedValue([])

  renderPage()
  fireEvent.click(await screen.findByText('Risotto'))
  fireEvent.click(await screen.findByRole('button', { name: /^share$/i }))
  await screen.findByText(/Anyone with the link can open this recipe/i)

  fireEvent.click(screen.getAllByLabelText('Close')[0])
  fireEvent.click(await screen.findByText('Risotto'))

  await screen.findByText(/Ingredients for/i)
  expect(screen.queryByText(/Anyone with the link can open this recipe/i)).toBeNull()
})

// AT-3/AT-7: a copied recipe credits its original author in the detail modal.
test('shows the attribution line for a copied recipe', async () => {
  recipesApi.fetchAll.mockResolvedValue([
    {
      id: 1,
      title: 'Risotto',
      course: 'main',
      tags: [],
      ingredients: [],
      procedure: '',
      source_author_username: 'nonna',
      source_recipe_title: 'Risotto alla Milanese',
    },
  ])
  tagsApi.fetchAll.mockResolvedValue([])
  ingredientsApi.fetchAll.mockResolvedValue([])

  renderPage()
  fireEvent.click(await screen.findByText('Risotto'))

  expect(
    await screen.findByText('Adapted from Risotto alla Milanese by @nonna')
  ).toBeInTheDocument()
})

test('shows no attribution line for an original recipe', async () => {
  recipesApi.fetchAll.mockResolvedValue([
    { id: 1, title: 'Risotto', course: 'main', tags: [], ingredients: [], procedure: '' },
  ])
  tagsApi.fetchAll.mockResolvedValue([])
  ingredientsApi.fetchAll.mockResolvedValue([])

  renderPage()
  fireEvent.click(await screen.findByText('Risotto'))
  await screen.findByText(/Ingredients for/i)

  expect(screen.queryByText(/^Adapted from/)).toBeNull()
})

// --- the empty book (RM-4 .. RM-7) -------------------------------------------

const loadEmptyBook = () => {
  recipesApi.fetchAll.mockResolvedValue([])
  tagsApi.fetchAll.mockResolvedValue([])
  ingredientsApi.fetchAll.mockResolvedValue([])
}

const libraryButton = () => screen.findByRole('button', { name: 'Browse the recipe library' })

// RM-6: the empty book points at Discover, the route to a populated book.
test('an empty book offers a way to the recipe library', async () => {
  loadEmptyBook()

  renderPage()

  expect(await libraryButton()).toBeInTheDocument()
})

test('the library call to action navigates to /discover', async () => {
  loadEmptyBook()

  renderPage()
  fireEvent.click(await libraryButton())

  expect(await screen.findByText('Discover page')).toBeInTheDocument()
})

// A failed load says nothing about the book: a network blip must not tell a
// user with fifty recipes that theirs is empty.
test('a failed load shows no library call to action', async () => {
  vi.spyOn(console, 'error').mockImplementation(() => {})
  recipesApi.fetchAll.mockRejectedValue(new Error('offline'))
  tagsApi.fetchAll.mockResolvedValue([])
  ingredientsApi.fetchAll.mockResolvedValue([])

  renderPage()
  // The tour gate flips once the load settles, failed or not (RM-5).
  await waitFor(() =>
    expect(screen.getByTestId('page-tour-recipes')).toHaveAttribute('data-enabled', 'true'),
  )

  expect(screen.queryByRole('button', { name: 'Browse the recipe library' })).toBeNull()
})

test('a book with recipes shows no library call to action', async () => {
  recipesApi.fetchAll.mockResolvedValue([{ id: 1, title: 'Risotto', course: 'main' }])
  tagsApi.fetchAll.mockResolvedValue([])
  ingredientsApi.fetchAll.mockResolvedValue([])

  renderPage()
  await screen.findByText('Risotto')

  expect(screen.queryByRole('button', { name: 'Browse the recipe library' })).toBeNull()
})

// RM-4: no modal of any kind opens on its own over an empty book.
test('an empty book opens no dialog', async () => {
  loadEmptyBook()

  renderPage()
  await libraryButton()

  expect(screen.queryByRole('dialog')).toBeNull()
})

// RM-4: the sessionStorage dismissal flag went with the modal it remembered.
test('the page does not touch sessionStorage', async () => {
  const touched = []
  for (const method of ['getItem', 'setItem', 'removeItem']) {
    const original = Storage.prototype[method]
    vi.spyOn(Storage.prototype, method).mockImplementation(function (...args) {
      if (this === window.sessionStorage) touched.push([method, ...args])
      return original.apply(this, args)
    })
  }
  loadEmptyBook()

  renderPage()
  await libraryButton()

  expect(touched).toEqual([])
})

// RM-7: the filtered-empty message stays about filters; the empty book is RM-6's.
test('an empty book never says no recipe matches the search', async () => {
  loadEmptyBook()

  renderPage()
  await libraryButton()
  fireEvent.change(screen.getByPlaceholderText('Search recipes…'), {
    target: { value: 'zzz' },
  })

  expect(screen.queryByText('No recipes match your search.')).toBeNull()
})

// RM-5: the tour waits for the first load, then runs -- on an empty account too.
test('the page tour is held back until the first load settles', async () => {
  let resolve
  recipesApi.fetchAll.mockReturnValue(new Promise((r) => { resolve = r }))
  tagsApi.fetchAll.mockResolvedValue([])
  ingredientsApi.fetchAll.mockResolvedValue([])

  renderPage()

  expect(screen.getByTestId('page-tour-recipes')).toHaveAttribute('data-enabled', 'false')
  resolve([])
  await waitFor(() =>
    expect(screen.getByTestId('page-tour-recipes')).toHaveAttribute('data-enabled', 'true'),
  )
})

test('the page tour is enabled on an empty account once loaded', async () => {
  loadEmptyBook()

  renderPage()
  await libraryButton()

  expect(screen.getByTestId('page-tour-recipes')).toHaveAttribute('data-enabled', 'true')
})

test('marks the first recipe card as the tutorial anchor, not the whole grid', async () => {
  recipesApi.fetchAll.mockResolvedValue([
    { id: 1, title: 'Spaghetti', course: 'main' },
    { id: 2, title: 'Pizza', course: 'main' },
  ])
  tagsApi.fetchAll.mockResolvedValue([])
  ingredientsApi.fetchAll.mockResolvedValue([])

  const { container } = renderPage()
  await screen.findByText('Spaghetti')

  const anchors = container.querySelectorAll('[data-tour="recipes-card"]')
  expect(anchors).toHaveLength(1)
  expect(anchors[0].textContent).toContain('Spaghetti')
})


// --- the servings basis -----------------------------------------------------

test('a recipe card says how many people its quantities are written for', async () => {
  recipesApi.fetchAll.mockResolvedValue([
    { id: 1, title: 'Ribollita', course: 'main', servings: 4, ingredients: [] },
  ])
  tagsApi.fetchAll.mockResolvedValue([])
  ingredientsApi.fetchAll.mockResolvedValue([])

  renderPage()

  await screen.findByText('Ribollita')
  expect(screen.getByText(/serves 4/i)).toBeInTheDocument()
})

test('the opened recipe says how many people its quantities are written for', async () => {
  recipesApi.fetchAll.mockResolvedValue([
    {
      id: 1,
      title: 'Ribollita',
      course: 'main',
      servings: 4,
      ingredients: [{ id: 1, name: 'Cavolo nero', amount: 800, unit: 'g' }],
    },
  ])
  tagsApi.fetchAll.mockResolvedValue([])
  ingredientsApi.fetchAll.mockResolvedValue([])

  renderPage()

  fireEvent.click(await screen.findByText('Ribollita'))

  await waitFor(() =>
    expect(screen.getAllByText(/ingredients for 4 people/i).length).toBeGreaterThan(0),
  )
})

// --- card meta line ---------------------------------------------------------

test('the card meta line is abbreviated on mobile so it fits one line', async () => {
  stubViewport(true)
  recipesApi.fetchAll.mockResolvedValue([
    {
      id: 1,
      title: 'Ribollita',
      course: 'main',
      servings: 4,
      tags: [],
      ingredients: [{ name: 'Cavolo nero' }, { name: 'Fagioli' }],
    },
  ])
  tagsApi.fetchAll.mockResolvedValue([])
  ingredientsApi.fetchAll.mockResolvedValue([])

  renderPage()

  expect(await screen.findByText('main · 2 ingr · 4p')).toBeInTheDocument()
})

test('the card meta line keeps full words on desktop', async () => {
  stubViewport(false)
  recipesApi.fetchAll.mockResolvedValue([
    {
      id: 1,
      title: 'Ribollita',
      course: 'main',
      servings: 4,
      tags: [],
      ingredients: [{ name: 'Cavolo nero' }, { name: 'Fagioli' }],
    },
  ])
  tagsApi.fetchAll.mockResolvedValue([])
  ingredientsApi.fetchAll.mockResolvedValue([])

  renderPage()

  expect(
    await screen.findByText('main · 2 ingredients · serves 4'),
  ).toBeInTheDocument()
})

test('cancelling the delete confirmation keeps the recipe', async () => {
  recipesApi.fetchAll.mockResolvedValue([
    { id: 1, title: 'Risotto', course: 'main', tags: [], ingredients: [], procedure: '' },
  ])
  tagsApi.fetchAll.mockResolvedValue([])
  ingredientsApi.fetchAll.mockResolvedValue([])
  recipesApi.delete = vi.fn().mockResolvedValue(null)

  renderPage()
  fireEvent.click(await screen.findByText('Risotto'))
  fireEvent.click(await screen.findByRole('button', { name: 'Delete' }))
  fireEvent.click(await screen.findByRole('button', { name: 'Cancel' }))

  expect(recipesApi.delete).not.toHaveBeenCalled()
  // Cancelling leaves the detail modal open, so the title is on screen twice:
  // the grid card behind it and the modal heading.
  expect(screen.getAllByText('Risotto')).toHaveLength(2)
})

// --- filters ----------------------------------------------------------------

test('filter options are buttons, not sub-floor checkboxes', async () => {
  recipesApi.fetchAll.mockResolvedValue([
    { id: 1, title: 'Spaghetti', course: 'main', tags: ['quick'], ingredients: [] },
  ])
  tagsApi.fetchAll.mockResolvedValue([{ name: 'quick' }])
  ingredientsApi.fetchAll.mockResolvedValue([])

  renderPage()
  await screen.findByText('Spaghetti')
  fireEvent.click(screen.getByLabelText('Filter'))
  fireEvent.click(screen.getByRole('button', { name: 'Tags' }))

  const chip = screen.getByRole('button', { name: 'quick' })
  expect(chip).toHaveAttribute('aria-pressed', 'false')

  fireEvent.click(chip)
  expect(screen.getByRole('button', { name: 'quick' })).toHaveAttribute(
    'aria-pressed',
    'true',
  )
})

test('the funnel counts the active filters', async () => {
  recipesApi.fetchAll.mockResolvedValue([
    { id: 1, title: 'Spaghetti', course: 'main', tags: ['quick'], ingredients: [] },
  ])
  tagsApi.fetchAll.mockResolvedValue([{ name: 'quick' }])
  ingredientsApi.fetchAll.mockResolvedValue([])

  renderPage()
  await screen.findByText('Spaghetti')

  // jest-dom's toHaveTextContent('') matches anything, so assert the negative
  // against the value that will appear rather than against emptiness.
  expect(screen.getByLabelText('Filter')).not.toHaveTextContent('1')

  fireEvent.click(screen.getByLabelText('Filter'))
  fireEvent.click(screen.getByRole('button', { name: 'Tags' }))
  fireEvent.click(screen.getByRole('button', { name: 'quick' }))

  expect(screen.getByLabelText('Filter')).toHaveTextContent('1')
})

test('an active filter shows as a removable chip', async () => {
  recipesApi.fetchAll.mockResolvedValue([
    { id: 1, title: 'Spaghetti', course: 'main', tags: ['quick'], ingredients: [] },
    { id: 2, title: 'Pizza', course: 'main', tags: [], ingredients: [] },
  ])
  tagsApi.fetchAll.mockResolvedValue([{ name: 'quick' }])
  ingredientsApi.fetchAll.mockResolvedValue([])

  renderPage()
  await screen.findByText('Spaghetti')
  fireEvent.click(screen.getByLabelText('Filter'))
  fireEvent.click(screen.getByRole('button', { name: 'Tags' }))
  fireEvent.click(screen.getByRole('button', { name: 'quick' }))

  expect(screen.queryByText('Pizza')).toBeNull()

  fireEvent.click(screen.getByRole('button', { name: 'Remove filter quick' }))

  expect(await screen.findByText('Pizza')).toBeInTheDocument()
})

test('clear all drops every filter at once', async () => {
  recipesApi.fetchAll.mockResolvedValue([
    { id: 1, title: 'Spaghetti', course: 'main', tags: ['quick'], ingredients: [] },
    { id: 2, title: 'Pizza', course: 'first-course', tags: [], ingredients: [] },
  ])
  tagsApi.fetchAll.mockResolvedValue([{ name: 'quick' }])
  ingredientsApi.fetchAll.mockResolvedValue([])

  renderPage()
  await screen.findByText('Spaghetti')
  fireEvent.click(screen.getByLabelText('Filter'))
  fireEvent.click(screen.getByRole('button', { name: 'Tags' }))
  fireEvent.click(screen.getByRole('button', { name: 'quick' }))
  fireEvent.click(screen.getByRole('button', { name: 'Course' }))
  fireEvent.click(screen.getByRole('button', { name: 'main' }))

  fireEvent.click(screen.getByRole('button', { name: 'Clear all filters' }))

  expect(await screen.findByText('Pizza')).toBeInTheDocument()
  expect(screen.getByLabelText('Filter')).not.toHaveTextContent('2')
})

test('Escape closes the filter popover', async () => {
  recipesApi.fetchAll.mockResolvedValue([
    { id: 1, title: 'Spaghetti', course: 'main', tags: [], ingredients: [] },
  ])
  tagsApi.fetchAll.mockResolvedValue([])
  ingredientsApi.fetchAll.mockResolvedValue([])

  renderPage()
  await screen.findByText('Spaghetti')
  fireEvent.click(screen.getByLabelText('Filter'))
  expect(screen.getByRole('button', { name: 'Course' })).toBeInTheDocument()

  fireEvent.keyDown(document, { key: 'Escape' })

  await waitFor(() =>
    expect(screen.queryByRole('button', { name: 'Course' })).toBeNull(),
  )
})

test('the filter opens a bottom sheet on mobile', async () => {
  stubViewport(true)
  recipesApi.fetchAll.mockResolvedValue([
    { id: 1, title: 'Spaghetti', course: 'main', tags: [], ingredients: [] },
  ])
  tagsApi.fetchAll.mockResolvedValue([])
  ingredientsApi.fetchAll.mockResolvedValue([])

  renderPage()
  await screen.findByText('Spaghetti')
  fireEvent.click(screen.getByLabelText('Filter'))

  expect(screen.getByRole('dialog', { name: 'Filters' })).toBeInTheDocument()
})

test('the filter stays a popover on desktop', async () => {
  stubViewport(false)
  recipesApi.fetchAll.mockResolvedValue([
    { id: 1, title: 'Spaghetti', course: 'main', tags: [], ingredients: [] },
  ])
  tagsApi.fetchAll.mockResolvedValue([])
  ingredientsApi.fetchAll.mockResolvedValue([])

  renderPage()
  await screen.findByText('Spaghetti')
  fireEvent.click(screen.getByLabelText('Filter'))

  expect(screen.queryByRole('dialog', { name: 'Filters' })).toBeNull()
  expect(screen.getByRole('button', { name: 'Course' })).toBeInTheDocument()
})

test('the sheet footer reports the filtered count and closes the sheet', async () => {
  stubViewport(true)
  recipesApi.fetchAll.mockResolvedValue([
    { id: 1, title: 'Spaghetti', course: 'main', tags: [], ingredients: [] },
    { id: 2, title: 'Pizza', course: 'main', tags: [], ingredients: [] },
  ])
  tagsApi.fetchAll.mockResolvedValue([])
  ingredientsApi.fetchAll.mockResolvedValue([])

  renderPage()
  await screen.findByText('Spaghetti')
  fireEvent.click(screen.getByLabelText('Filter'))

  fireEvent.click(screen.getByRole('button', { name: 'Show 2 recipes' }))

  await waitFor(() =>
    expect(screen.queryByRole('dialog', { name: 'Filters' })).toBeNull(),
  )
})

// --- mobile header ----------------------------------------------------------

test('the mobile header holds only search and filter', async () => {
  stubViewport(true)
  recipesApi.fetchAll.mockResolvedValue([
    { id: 1, title: 'Spaghetti', course: 'main', tags: [], ingredients: [] },
  ])
  tagsApi.fetchAll.mockResolvedValue([])
  ingredientsApi.fetchAll.mockResolvedValue([])

  renderPage()
  await screen.findByText('Spaghetti')

  expect(screen.queryByRole('button', { name: 'Import from web' })).toBeNull()
  expect(screen.queryByRole('button', { name: /^New recipe$/ })).toBeNull()
  expect(screen.getByLabelText('Filter')).toBeInTheDocument()
})

test('the mobile add button offers both ways to create a recipe', async () => {
  stubViewport(true)
  recipesApi.fetchAll.mockResolvedValue([
    { id: 1, title: 'Spaghetti', course: 'main', tags: [], ingredients: [] },
  ])
  tagsApi.fetchAll.mockResolvedValue([])
  ingredientsApi.fetchAll.mockResolvedValue([])

  renderPage()
  await screen.findByText('Spaghetti')

  fireEvent.click(screen.getByRole('button', { name: 'Add a recipe' }))

  expect(screen.getByRole('button', { name: 'Write it myself' })).toBeInTheDocument()
  expect(
    screen.getByRole('button', { name: 'Import from a website' }),
  ).toBeInTheDocument()
})

test('the add sheet opens the import dialog', async () => {
  stubViewport(true)
  recipesApi.fetchAll.mockResolvedValue([
    { id: 1, title: 'Spaghetti', course: 'main', tags: [], ingredients: [] },
  ])
  tagsApi.fetchAll.mockResolvedValue([])
  ingredientsApi.fetchAll.mockResolvedValue([])

  renderPage()
  await screen.findByText('Spaghetti')

  fireEvent.click(screen.getByRole('button', { name: 'Add a recipe' }))
  fireEvent.click(screen.getByRole('button', { name: 'Import from a website' }))

  // The add sheet gives way to the import dialog rather than stacking.
  await waitFor(() =>
    expect(screen.queryByRole('button', { name: 'Write it myself' })).toBeNull(),
  )
})

test('desktop keeps both header buttons and shows no FAB', async () => {
  stubViewport(false)
  recipesApi.fetchAll.mockResolvedValue([
    { id: 1, title: 'Spaghetti', course: 'main', tags: [], ingredients: [] },
  ])
  tagsApi.fetchAll.mockResolvedValue([])
  ingredientsApi.fetchAll.mockResolvedValue([])

  renderPage()
  await screen.findByText('Spaghetti')

  expect(screen.getByRole('button', { name: 'Import from web' })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: /New recipe/ })).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Add a recipe' })).toBeNull()
})

test('says so when no recipe matches the search', async () => {
  recipesApi.fetchAll.mockResolvedValue([
    { id: 1, title: 'Spaghetti', course: 'main', tags: [], ingredients: [] },
  ])
  tagsApi.fetchAll.mockResolvedValue([])
  ingredientsApi.fetchAll.mockResolvedValue([])

  renderPage()
  await screen.findByText('Spaghetti')

  fireEvent.change(screen.getByPlaceholderText('Search recipes…'), {
    target: { value: 'zzz' },
  })

  expect(screen.getByText('No recipes match your search.')).toBeInTheDocument()
})

test('the empty state clears the search and the filters together', async () => {
  recipesApi.fetchAll.mockResolvedValue([
    { id: 1, title: 'Spaghetti', course: 'main', tags: ['quick'], ingredients: [] },
  ])
  tagsApi.fetchAll.mockResolvedValue([{ name: 'quick' }])
  ingredientsApi.fetchAll.mockResolvedValue([])

  renderPage()
  await screen.findByText('Spaghetti')
  fireEvent.click(screen.getByLabelText('Filter'))
  fireEvent.click(screen.getByRole('button', { name: 'Course' }))
  fireEvent.click(screen.getByRole('button', { name: 'main' }))
  fireEvent.change(screen.getByPlaceholderText('Search recipes…'), {
    target: { value: 'zzz' },
  })

  fireEvent.click(screen.getByRole('button', { name: 'Clear search and filters' }))

  expect(await screen.findByText('Spaghetti')).toBeInTheDocument()
  expect(screen.getByPlaceholderText('Search recipes…')).toHaveValue('')
  expect(screen.getByLabelText('Filter')).not.toHaveTextContent('1')
})

// An account's ingredient catalogue is the one filter list long enough that
// showing all of it is the problem; course and tags are short.
test('only the ingredient filter is searchable', async () => {
  recipesApi.fetchAll.mockResolvedValue([
    {
      id: 1,
      title: 'Spaghetti',
      tags: ['Italian'],
      ingredients: [{ name: 'Tomato' }],
      course: 'main',
    },
  ])
  tagsApi.fetchAll.mockResolvedValue([{ name: 'Italian' }])
  ingredientsApi.fetchAll.mockResolvedValue([
    { id: 1, name: 'Tomato' },
    { id: 2, name: 'Lettuce' },
  ])

  renderPage()
  await screen.findByText('Spaghetti')
  fireEvent.click(screen.getByLabelText('Filter'))

  fireEvent.click(screen.getByRole('button', { name: 'Ingredients' }))
  expect(screen.queryByRole('button', { name: 'Lettuce' })).toBeNull()
  fireEvent.change(screen.getByPlaceholderText('Search Ingredients…'), {
    target: { value: 'let' },
  })
  expect(screen.getByRole('button', { name: 'Lettuce' })).toBeInTheDocument()

  fireEvent.click(screen.getByRole('button', { name: 'Tags' }))
  expect(screen.getByRole('button', { name: 'Italian' })).toBeInTheDocument()
  expect(screen.queryByPlaceholderText(/^Search Tags/)).toBeNull()
})

test('shows the recipe score on the card, and in the detail view', async () => {
  recipesApi.fetchAll.mockResolvedValue([
    { id: 1, title: 'Spaghetti', course: 'main', score: 7.4239 },
  ])
  tagsApi.fetchAll.mockResolvedValue([])
  ingredientsApi.fetchAll.mockResolvedValue([])

  renderPage()

  const title = await screen.findByText('Spaghetti')
  expect(screen.getByText('7.42')).toBeInTheDocument()

  fireEvent.click(title)

  expect(await screen.findByText(/main · 7\.42/)).toBeInTheDocument()
})

test('shows a zero score when the recipe has none', async () => {
  recipesApi.fetchAll.mockResolvedValue([
    { id: 1, title: 'Spaghetti', course: 'main' },
  ])
  tagsApi.fetchAll.mockResolvedValue([])
  ingredientsApi.fetchAll.mockResolvedValue([])

  renderPage()

  await screen.findByText('Spaghetti')
  expect(screen.getByText('0.00')).toBeInTheDocument()
})

test('sorts recipes by score, name and course, and flips direction', async () => {
  recipesApi.fetchAll.mockResolvedValue([
    { id: 1, title: 'Zuppa', course: 'first-course', score: 0.2 },
    { id: 2, title: 'Burger', course: 'main', score: 0.9 },
    { id: 3, title: 'Salad', course: 'side', score: 0.5 },
  ])
  tagsApi.fetchAll.mockResolvedValue([])
  ingredientsApi.fetchAll.mockResolvedValue([])

  renderPage()
  await screen.findByText('Zuppa')

  const order = () =>
    [
      ...document
        .querySelector('[data-tour="recipes-grid"]')
        .querySelectorAll('[data-testid="recipe-title"]'),
    ].map((el) => el.textContent)

  expect(order()).toEqual(['Zuppa', 'Burger', 'Salad'])

  const select = screen.getByLabelText('Sort recipes')
  fireEvent.change(select, { target: { value: 'score' } })
  await waitFor(() => expect(order()).toEqual(['Burger', 'Salad', 'Zuppa']))

  fireEvent.click(screen.getByLabelText('Sort ascending'))
  await waitFor(() => expect(order()).toEqual(['Zuppa', 'Salad', 'Burger']))

  fireEvent.change(select, { target: { value: 'name' } })
  await waitFor(() => expect(order()).toEqual(['Burger', 'Salad', 'Zuppa']))

  fireEvent.change(select, { target: { value: 'course' } })
  await waitFor(() => expect(order()).toEqual(['Burger', 'Zuppa', 'Salad']))
})

test('sorting applies to the filtered recipes', async () => {
  recipesApi.fetchAll.mockResolvedValue([
    { id: 1, title: 'Sea bass', course: 'main', score: 0.1 },
    { id: 2, title: 'Sausage', course: 'main', score: 0.8 },
    { id: 3, title: 'Pizza', course: 'main', score: 0.9 },
  ])
  tagsApi.fetchAll.mockResolvedValue([])
  ingredientsApi.fetchAll.mockResolvedValue([])

  renderPage()
  await screen.findByText('Pizza')

  fireEvent.change(screen.getByPlaceholderText('Search recipes…'), {
    target: { value: 'sea' },
  })
  fireEvent.change(screen.getByLabelText('Sort recipes'), { target: { value: 'score' } })

  await waitFor(() => {
    const shown = [
      ...document
        .querySelector('[data-tour="recipes-grid"]')
        .querySelectorAll('[data-testid="recipe-title"]'),
    ].map((el) => el.textContent)
    expect(shown).toEqual(['Sea bass'])
  })
})
