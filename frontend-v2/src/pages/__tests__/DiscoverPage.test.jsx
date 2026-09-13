/**
 * @vitest-environment jsdom
 */
import React from 'react'
import { render, screen, fireEvent, waitFor, within, cleanup } from '@testing-library/react'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import '@testing-library/jest-dom/vitest'
import DiscoverPage from '../DiscoverPage'
import { catalogApi } from '../../api/catalogApi'
import { tagsApi } from '../../api/tagsApi'
import { AuthContext } from '../../auth/AuthContext'
import { stubViewport } from '../../test/stubViewport'

vi.mock('../../api/catalogApi', () => ({
  catalogApi: {
    list: vi.fn(),
    get: vi.fn(),
    adopt: vi.fn(),
  },
}))

vi.mock('../../api/tagsApi', () => ({
  tagsApi: {
    fetchAll: vi.fn(),
  },
}))

function row(overrides) {
  return {
    id: 1,
    title: 'Spaghetti al pomodoro',
    course: 'first-course',
    servings: 1,
    bulk_prep: false,
    image_url: null,
    tags: ['pasta'],
    ingredients: [{ name: 'Pasta', quantity: 80, unit: 'g' }],
    adoption_count: 0,
    in_my_book: false,
    ...overrides,
  }
}

const ROWS = [
  row({ id: 1, title: 'Spaghetti al pomodoro', adoption_count: 12 }),
  row({ id: 2, title: 'Roast chicken', course: 'main', adoption_count: 7, tags: ['meat'] }),
  row({ id: 3, title: 'Green salad', course: 'side', adoption_count: 3, tags: ['vegan'] }),
  row({ id: 4, title: 'Lentil soup', course: 'main', adoption_count: 1, in_my_book: true }),
]

// The most recent `list` call's filter argument.
const lastListArgs = () => catalogApi.list.mock.calls.at(-1)[0]

// The card whose title is `title`.
const cardFor = (title) => screen.getByText(title).closest('[data-testid="catalog-card"]')

async function renderLoaded(ui = <DiscoverPage />) {
  render(ui)
  await screen.findByText('Spaghetti al pomodoro')
}

beforeEach(() => {
  // The dish-glyph Icon fetches SVGs from a CDN; keep tests hermetic.
  globalThis.fetch = vi.fn(() => Promise.reject(new Error('no network')))
  stubViewport(false)
  catalogApi.list.mockResolvedValue(ROWS)
  tagsApi.fetchAll.mockResolvedValue([
    { id: 1, name: 'vegan', is_system: true },
    { id: 2, name: 'quick', is_system: true },
    { id: 3, name: 'my-own-tag', is_system: false },
  ])
})

afterEach(() => {
  vi.clearAllMocks()
  cleanup()
})

// --- Listing ----------------------------------------------------------------

test('renders a card per catalog row', async () => {
  await renderLoaded()
  expect(screen.getAllByTestId('catalog-card')).toHaveLength(4)
  expect(screen.getByText('Roast chicken')).toBeInTheDocument()
})

test('each card shows its adoption count as a bare number (UI-13)', async () => {
  await renderLoaded()
  const count = within(cardFor('Roast chicken')).getByLabelText('Added 7 times')
  expect(count).toHaveTextContent(/^7$/)
})

test('loads the most-added order by default', async () => {
  await renderLoaded()
  expect(catalogApi.list).toHaveBeenCalledWith(expect.objectContaining({ sort: 'popular' }))
  expect(screen.getByLabelText('Sort recipes')).toHaveValue('popular')
  expect(screen.getByRole('option', { name: 'Most added' })).toBeInTheDocument()
})

test('changing the sort refetches with sort=title', async () => {
  await renderLoaded()
  fireEvent.change(screen.getByLabelText('Sort recipes'), { target: { value: 'title' } })
  await waitFor(() => expect(lastListArgs()).toEqual(expect.objectContaining({ sort: 'title' })))
})

test('the sort has no direction arrow: each ordering is fixed server-side', async () => {
  await renderLoaded()
  expect(screen.queryByLabelText(/sort (ascending|descending)/i)).not.toBeInTheDocument()
})

// --- Filtering & search -----------------------------------------------------

async function openFilterGroup(label) {
  if (!screen.queryByRole('button', { name: label })) {
    fireEvent.click(screen.getByRole('button', { name: 'Filter' }))
  }
  fireEvent.click(screen.getByRole('button', { name: label }))
}

test('a course filter refetches with that course', async () => {
  await renderLoaded()
  await openFilterGroup('Course')
  // Every course the catalog accepts is offered, whether or not it is listed.
  expect(screen.getByRole('button', { name: 'main' })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'first-course' })).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'side' }))
  await waitFor(() => expect(lastListArgs()).toEqual(expect.objectContaining({ courses: ['side'] })))
})

test('tag filters offer only system tags and refetch with every selected tag', async () => {
  await renderLoaded()
  await openFilterGroup('Tags')
  expect(screen.queryByRole('button', { name: 'my-own-tag' })).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'vegan' }))
  fireEvent.click(screen.getByRole('button', { name: 'quick' }))
  await waitFor(() =>
    expect(lastListArgs()).toEqual(expect.objectContaining({ tags: ['vegan', 'quick'] })),
  )
})

test('an active filter chip removes its filter', async () => {
  await renderLoaded()
  await openFilterGroup('Course')
  fireEvent.click(screen.getByRole('button', { name: 'side' }))
  await waitFor(() => expect(lastListArgs().courses).toEqual(['side']))

  fireEvent.click(screen.getByRole('button', { name: 'Remove filter side' }))

  await waitFor(() => expect(lastListArgs().courses).toEqual([]))
  expect(screen.queryByRole('button', { name: 'Remove filter side' })).not.toBeInTheDocument()
})

test('search is debounced: only the settled text is sent as q', async () => {
  await renderLoaded()
  const input = screen.getByPlaceholderText('Search the library…')
  fireEvent.change(input, { target: { value: 'pa' } })
  fireEvent.change(input, { target: { value: 'pas' } })
  fireEvent.change(input, { target: { value: 'pasta' } })

  await waitFor(() => expect(lastListArgs()).toEqual(expect.objectContaining({ q: 'pasta' })))
  const sentQueries = catalogApi.list.mock.calls.map(([args]) => args.q)
  expect(sentQueries).not.toContain('pa')
  expect(sentQueries).not.toContain('pas')
})

test('on mobile the filters open in a bottom sheet', async () => {
  stubViewport(true)
  await renderLoaded()
  fireEvent.click(screen.getByRole('button', { name: 'Filter' }))
  const sheet = screen.getByRole('dialog', { name: 'Filters' })
  expect(within(sheet).getByRole('button', { name: 'Course' })).toBeInTheDocument()
})

// --- Detail -----------------------------------------------------------------

test('opening a card shows its ingredients and procedure from catalogApi.get (UI-7)', async () => {
  catalogApi.get.mockResolvedValue({
    ...ROWS[1],
    servings: 2,
    ingredients: [
      { name: 'Chicken', quantity: 1, unit: 'piece' },
      { name: 'Rosemary', quantity: 5, unit: 'g' },
    ],
    procedure: 'Roast for an hour.',
  })
  await renderLoaded()

  fireEvent.click(screen.getByRole('button', { name: /Roast chicken/ }))

  expect(catalogApi.get).toHaveBeenCalledWith(2)
  // The shared Modal carries no dialog role; its heading is the recipe title.
  expect(await screen.findByRole('heading', { name: 'Roast chicken' })).toBeInTheDocument()
  expect(await screen.findByText('Roast for an hour.')).toBeInTheDocument()
  expect(screen.getByText(/Chicken/)).toBeInTheDocument()
  expect(screen.getByText(/Rosemary/)).toBeInTheDocument()
  expect(screen.getByText('5 g')).toBeInTheDocument()
  expect(screen.getByText(/Ingredients for 2 people/)).toBeInTheDocument()
})

test('a detail that fails to load says so', async () => {
  catalogApi.get.mockRejectedValue(new Error('Not found'))
  await renderLoaded()

  fireEvent.click(screen.getByRole('button', { name: /Roast chicken/ }))

  expect(await screen.findByRole('alert')).toHaveTextContent(/couldn.t load this recipe/i)
})

// --- Selection --------------------------------------------------------------

test('selecting two cards offers "Add 2 recipes" in a 44px action', async () => {
  await renderLoaded()
  expect(screen.queryByRole('button', { name: /^Add \d+ recipes?$/ })).not.toBeInTheDocument()

  fireEvent.click(screen.getByRole('checkbox', { name: 'Select Spaghetti al pomodoro' }))
  expect(screen.getByRole('button', { name: 'Add 1 recipe' })).toBeInTheDocument()
  fireEvent.click(screen.getByRole('checkbox', { name: 'Select Roast chicken' }))

  const add = screen.getByRole('button', { name: 'Add 2 recipes' })
  expect(add).toHaveClass('min-h-11')
  // Ticking a box must not also open the card.
  expect(catalogApi.get).not.toHaveBeenCalled()
})

test('a card already in the book shows "In your book" and cannot be selected (UI-8/9)', async () => {
  await renderLoaded()
  const held = cardFor('Lentil soup')
  expect(within(held).getByText('In your book')).toBeInTheDocument()
  expect(within(held).queryByRole('checkbox')).not.toBeInTheDocument()
  expect(within(cardFor('Green salad')).queryByText('In your book')).not.toBeInTheDocument()
})

test('unticking a card takes it back out of the count', async () => {
  await renderLoaded()
  const box = screen.getByRole('checkbox', { name: 'Select Green salad' })
  fireEvent.click(box)
  fireEvent.click(box)
  expect(screen.queryByRole('button', { name: /^Add \d+ recipes?$/ })).not.toBeInTheDocument()
})

// --- Adding -----------------------------------------------------------------

test('adding adopts the selection, confirms it, refetches and clears the selection', async () => {
  catalogApi.adopt.mockResolvedValue({ created_ids: [101, 102], skipped_ids: [] })
  await renderLoaded()
  fireEvent.click(screen.getByRole('checkbox', { name: 'Select Spaghetti al pomodoro' }))
  fireEvent.click(screen.getByRole('checkbox', { name: 'Select Green salad' }))
  const listCalls = catalogApi.list.mock.calls.length

  fireEvent.click(screen.getByRole('button', { name: 'Add 2 recipes' }))

  expect(await screen.findByRole('status')).toHaveTextContent(/added 2 recipes to your book/i)
  expect(catalogApi.adopt).toHaveBeenCalledWith([1, 3])
  await waitFor(() => expect(catalogApi.list.mock.calls.length).toBeGreaterThan(listCalls))
  expect(screen.queryByRole('button', { name: /^Add \d+ recipes?$/ })).not.toBeInTheDocument()
  expect(screen.getByRole('checkbox', { name: 'Select Green salad' })).not.toBeChecked()
})

test('the add action shows progress while the request is in flight', async () => {
  let resolve
  catalogApi.adopt.mockReturnValue(new Promise((r) => { resolve = r }))
  await renderLoaded()
  fireEvent.click(screen.getByRole('checkbox', { name: 'Select Green salad' }))

  fireEvent.click(screen.getByRole('button', { name: 'Add 1 recipe' }))

  expect(await screen.findByRole('button', { name: /adding/i })).toBeDisabled()
  resolve({ created_ids: [9], skipped_ids: [] })
  expect(await screen.findByRole('status')).toBeInTheDocument()
})

test('a failed add names the failure and keeps the selection (UI-15)', async () => {
  catalogApi.adopt.mockRejectedValue(new Error('Rate limit exceeded'))
  await renderLoaded()
  fireEvent.click(screen.getByRole('checkbox', { name: 'Select Spaghetti al pomodoro' }))
  fireEvent.click(screen.getByRole('checkbox', { name: 'Select Green salad' }))

  fireEvent.click(screen.getByRole('button', { name: 'Add 2 recipes' }))

  const alert = await screen.findByRole('alert')
  expect(alert).toHaveTextContent(/couldn.t add/i)
  expect(alert).toHaveTextContent('Rate limit exceeded')
  expect(screen.getByRole('button', { name: 'Add 2 recipes' })).toBeEnabled()
  expect(screen.getByRole('checkbox', { name: 'Select Green salad' })).toBeChecked()
})

// --- Empty & error states ---------------------------------------------------

test('an empty library says so instead of rendering a blank page (UI-14)', async () => {
  catalogApi.list.mockResolvedValue([])
  render(<DiscoverPage />)
  expect(await screen.findByText(/the recipe library is empty/i)).toBeInTheDocument()
})

test('a search with no results offers to clear it', async () => {
  await renderLoaded()
  catalogApi.list.mockResolvedValue([])
  fireEvent.change(screen.getByPlaceholderText('Search the library…'), {
    target: { value: 'zzz' },
  })

  expect(await screen.findByText(/no recipes match/i)).toBeInTheDocument()
  catalogApi.list.mockResolvedValue(ROWS)
  fireEvent.click(screen.getByRole('button', { name: /clear search and filters/i }))
  await waitFor(() => expect(lastListArgs().q).toBe(''))
  expect(await screen.findByText('Roast chicken')).toBeInTheDocument()
})

test('a failed load shows an error with a retry (UI-14)', async () => {
  catalogApi.list.mockRejectedValueOnce(new Error('boom'))
  render(<DiscoverPage />)

  expect(await screen.findByRole('alert')).toHaveTextContent(/couldn.t load the recipe library/i)
  fireEvent.click(screen.getByRole('button', { name: /try again/i }))
  expect(await screen.findByText('Roast chicken')).toBeInTheDocument()
})

// --- No admin controls (T10 adds them) --------------------------------------

test('renders no admin controls, even for an admin (UI-11)', async () => {
  await renderLoaded(
    <AuthContext.Provider value={{ user: { username: 'demo', is_admin: true } }}>
      <DiscoverPage />
    </AuthContext.Provider>,
  )
  const adminish = /new catalog recipe|edit|publish|retire|retired|export/i
  expect(screen.queryAllByRole('button', { name: adminish })).toHaveLength(0)
  expect(screen.queryAllByRole('checkbox', { name: adminish })).toHaveLength(0)
  expect(document.body.textContent).not.toMatch(/publish|retire|export/i)
})
