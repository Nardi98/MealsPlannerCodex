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
import { ingredientsApi } from '../../api/ingredientsApi'
import { AuthContext } from '../../auth/AuthContext'
import { stubViewport } from '../../test/stubViewport'

// The row <-> form mappers stay real; only the network calls are mocked.
vi.mock('../../api/catalogApi', async (importOriginal) => ({
  ...(await importOriginal()),
  catalogApi: {
    list: vi.fn(),
    get: vi.fn(),
    adopt: vi.fn(),
    admin: {
      list: vi.fn(),
      create: vi.fn(),
      update: vi.fn(),
      publish: vi.fn(),
      retire: vi.fn(),
      exportCatalog: vi.fn(),
      ingredients: vi.fn(),
      tags: vi.fn(),
    },
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
  ingredientsApi.fetchAll.mockResolvedValue([])
  catalogApi.admin.list.mockResolvedValue(ADMIN_ROWS)
  catalogApi.admin.ingredients.mockResolvedValue([])
  catalogApi.admin.tags.mockResolvedValue([])
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

test('the selection is locked while an add is in flight', async () => {
  let resolve
  catalogApi.adopt.mockReturnValue(new Promise((r) => { resolve = r }))
  await renderLoaded()
  fireEvent.click(screen.getByRole('checkbox', { name: 'Select Spaghetti al pomodoro' }))
  fireEvent.click(screen.getByRole('checkbox', { name: 'Select Green salad' }))

  fireEvent.click(screen.getByRole('button', { name: 'Add 2 recipes' }))
  await screen.findByRole('button', { name: /adding/i })

  const late = screen.getByRole('checkbox', { name: 'Select Roast chicken' })
  expect(late).toBeDisabled()
  expect(screen.getByRole('checkbox', { name: 'Select Green salad' })).toBeDisabled()
  fireEvent.click(late)
  expect(late).not.toBeChecked()
  expect(catalogApi.adopt).toHaveBeenCalledWith([1, 3])

  resolve({ created_ids: [101, 102], skipped_ids: [] })

  expect(await screen.findByRole('status')).toHaveTextContent(/added 2 recipes to your book/i)
  expect(screen.getByRole('checkbox', { name: 'Select Roast chicken' })).toBeEnabled()
  expect(screen.getByRole('checkbox', { name: 'Select Roast chicken' })).not.toBeChecked()
  expect(screen.queryByRole('button', { name: /^Add \d+ recipes?$/ })).not.toBeInTheDocument()
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

// --- Admin: nothing for anyone else (UI-11) ---------------------------------

const withUser = (user) => (
  <AuthContext.Provider value={{ user }}>
    <DiscoverPage />
  </AuthContext.Provider>
)

const ADMINISH = /new catalog recipe|edit|publish|retire|retired|export|delete/i

function expectNoAdminTrace() {
  expect(screen.queryAllByRole('button', { name: ADMINISH })).toHaveLength(0)
  expect(screen.queryAllByRole('checkbox', { name: ADMINISH })).toHaveLength(0)
  expect(document.body.textContent).not.toMatch(/catalog recipe|publish|retire|export/i)
}

test.each([
  ['no auth provider', <DiscoverPage key="none" />],
  ['no signed-in user', withUser(null)],
  ['is_admin missing', withUser({ username: 'friend' })],
  ['is_admin false', withUser({ username: 'friend', is_admin: false })],
])('%s: no admin controls anywhere, detail view included (UI-11)', async (_label, ui) => {
  catalogApi.get.mockResolvedValue({ ...ROWS[1], procedure: 'Roast for an hour.' })
  await renderLoaded(ui)
  expectNoAdminTrace()

  fireEvent.click(screen.getByRole('button', { name: /Roast chicken/ }))
  await screen.findByText('Roast for an hour.')

  expectNoAdminTrace()
  expect(catalogApi.admin.list).not.toHaveBeenCalled()
})

// --- Admin controls (UI-12) -------------------------------------------------

const ADMIN = { username: 'demo', is_admin: true }

function adminRow(overrides) {
  // AdminRow = CatalogRow − in_my_book + {procedure, status, published_at, retired_at}.
  // eslint-disable-next-line no-unused-vars
  const { in_my_book, ...rest } = row(overrides)
  return {
    procedure: 'Cook it.',
    status: 'published',
    published_at: '2026-09-01T10:00:00Z',
    retired_at: null,
    ...rest,
    ...overrides,
  }
}

const ADMIN_ROWS = [
  adminRow({ id: 1, title: 'Spaghetti al pomodoro', adoption_count: 12 }),
  adminRow({
    id: 9,
    title: 'Old stew',
    course: 'main',
    adoption_count: 5,
    status: 'retired',
    retired_at: '2026-09-10T10:00:00Z',
  }),
]

const renderAdmin = () => renderLoaded(withUser(ADMIN))

const adminListing = () => screen.findByRole('list', { name: 'All library entries' })
const adminItemFor = async (title) =>
  within(await adminListing()).getByText(title).closest('li')

// Fills the fields a catalog recipe needs and saves the open form.
function fillAndSave({ title }) {
  fireEvent.change(screen.getByLabelText('Title'), { target: { value: title } })
  fireEvent.change(screen.getByLabelText('Course'), { target: { value: 'main' } })
  fireEvent.click(screen.getByRole('button', { name: 'Save' }))
}

test('an admin sees the toolbar: new recipe, show retired and export', async () => {
  await renderAdmin()
  expect(screen.getByRole('button', { name: /new catalog recipe/i })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: /show retired/i })).toHaveAttribute('aria-pressed', 'false')
  expect(screen.getByRole('button', { name: /export/i })).toBeInTheDocument()
})

test('on a phone the admin toolbar keeps 44px tap targets', async () => {
  stubViewport(true)
  await renderAdmin()
  for (const name of [/new catalog recipe/i, /show retired/i, /export/i]) {
    expect(screen.getByRole('button', { name })).toHaveClass('min-h-11')
  }
})

test('"New catalog recipe" opens the form on the library sources, with no pantry writes', async () => {
  catalogApi.admin.ingredients.mockResolvedValue([
    { id: 50, name: 'Cavolo nero', season_months: [], grams_per_ml: null, grams_per_piece: null, preferred_dimension: null },
  ])
  catalogApi.admin.tags.mockResolvedValue([{ id: 60, name: 'soup' }])
  await renderAdmin()
  const pageTagLoads = tagsApi.fetchAll.mock.calls.length

  fireEvent.click(screen.getByRole('button', { name: /new catalog recipe/i }))

  expect(screen.getByRole('heading', { name: 'New catalog recipe' })).toBeInTheDocument()
  await waitFor(() => expect(catalogApi.admin.ingredients).toHaveBeenCalled())
  expect(catalogApi.admin.tags).toHaveBeenCalled()
  expect(ingredientsApi.fetchAll).not.toHaveBeenCalled()
  expect(tagsApi.fetchAll).toHaveBeenCalledTimes(pageTagLoads)
  fireEvent.focus(screen.getByPlaceholderText('ingredient'))
  expect(await screen.findByText('Cavolo nero')).toBeInTheDocument()
  expect(screen.queryByText(/add new ingredient/i)).not.toBeInTheDocument()
})

test('the catalog form offers library tags only, never a free-text new tag', async () => {
  catalogApi.admin.tags.mockResolvedValue([{ id: 60, name: 'soup' }])
  await renderAdmin()
  fireEvent.click(screen.getByRole('button', { name: /new catalog recipe/i }))
  await waitFor(() => expect(catalogApi.admin.tags).toHaveBeenCalled())

  const tagInput = screen.getByPlaceholderText('tag')
  fireEvent.focus(tagInput)
  fireEvent.change(tagInput, { target: { value: 'so' } })

  expect(await screen.findByText('soup')).toBeInTheDocument()
  expect(screen.queryByText(/^Add "/)).not.toBeInTheDocument()
})

test('saving a new catalog recipe calls admin.create, confirms it and refetches', async () => {
  catalogApi.admin.create.mockResolvedValue(adminRow({ id: 30, title: 'Ribollita' }))
  await renderAdmin()
  const listCalls = catalogApi.list.mock.calls.length
  fireEvent.click(screen.getByRole('button', { name: /new catalog recipe/i }))

  fillAndSave({ title: 'Ribollita' })

  await waitFor(() => expect(catalogApi.admin.create).toHaveBeenCalledTimes(1))
  expect(catalogApi.admin.create).toHaveBeenCalledWith(
    expect.objectContaining({ title: 'Ribollita', course: 'main', servings: 1 }),
  )
  expect(await screen.findByRole('status')).toHaveTextContent(/saved .*ribollita/i)
  await waitFor(() => expect(catalogApi.list.mock.calls.length).toBeGreaterThan(listCalls))
  expect(catalogApi.admin.update).not.toHaveBeenCalled()
})

test('Edit from the detail view pre-fills the whole recipe and calls admin.update', async () => {
  catalogApi.get.mockResolvedValue({
    ...ROWS[1],
    servings: 2,
    bulk_prep: true,
    ingredients: [{ name: 'Chicken', quantity: 1, unit: 'piece' }],
    procedure: 'Roast for an hour.',
  })
  catalogApi.admin.update.mockResolvedValue(adminRow({ id: 2, title: 'Roast chicken, lemon' }))
  await renderAdmin()
  const listCalls = catalogApi.list.mock.calls.length

  fireEvent.click(screen.getByRole('button', { name: /Roast chicken/ }))
  await screen.findByText('Roast for an hour.')
  fireEvent.click(screen.getByRole('button', { name: 'Edit' }))

  expect(screen.getByRole('heading', { name: 'Edit catalog recipe' })).toBeInTheDocument()
  expect(screen.getByLabelText('Title')).toHaveValue('Roast chicken')
  expect(screen.getByDisplayValue('Roast for an hour.')).toBeInTheDocument()
  expect(screen.getByPlaceholderText('ingredient')).toHaveValue('Chicken')
  expect(screen.getByLabelText('Serves')).toHaveValue(2)

  fireEvent.change(screen.getByLabelText('Title'), { target: { value: 'Roast chicken, lemon' } })
  fireEvent.click(screen.getByRole('button', { name: 'Save' }))

  await waitFor(() => expect(catalogApi.admin.update).toHaveBeenCalledTimes(1))
  expect(catalogApi.admin.update).toHaveBeenCalledWith(
    2,
    expect.objectContaining({
      title: 'Roast chicken, lemon',
      course: 'main',
      servings: 2,
      hot: true,
      procedure: 'Roast for an hour.',
      tags: ['meat'],
      ingredients: [expect.objectContaining({ name: 'Chicken', amount: 1, unit: 'piece' })],
    }),
  )
  expect(catalogApi.admin.create).not.toHaveBeenCalled()
  await waitFor(() => expect(catalogApi.list.mock.calls.length).toBeGreaterThan(listCalls))
})

test('Retire from the detail view retires it, closes the detail and refetches', async () => {
  catalogApi.get.mockResolvedValue({ ...ROWS[1], procedure: 'Roast for an hour.' })
  catalogApi.admin.retire.mockResolvedValue(adminRow({ id: 2, status: 'retired' }))
  await renderAdmin()
  const listCalls = catalogApi.list.mock.calls.length

  fireEvent.click(screen.getByRole('button', { name: /Roast chicken/ }))
  await screen.findByText('Roast for an hour.')
  fireEvent.click(screen.getByRole('button', { name: 'Retire' }))

  await waitFor(() => expect(catalogApi.admin.retire).toHaveBeenCalledWith(2))
  expect(await screen.findByRole('status')).toHaveTextContent(/retired .*roast chicken/i)
  expect(screen.queryByText('Roast for an hour.')).not.toBeInTheDocument()
  await waitFor(() => expect(catalogApi.list.mock.calls.length).toBeGreaterThan(listCalls))
})

test('"Show retired" loads the admin listing in a separate request, with a status per row (UI-16)', async () => {
  await renderAdmin()
  const userListCalls = catalogApi.list.mock.calls.length
  expect(catalogApi.admin.list).not.toHaveBeenCalled()

  fireEvent.click(screen.getByRole('button', { name: /show retired/i }))

  await waitFor(() => expect(catalogApi.admin.list).toHaveBeenCalledTimes(1))
  expect(screen.getByRole('button', { name: /show retired/i })).toHaveAttribute('aria-pressed', 'true')
  // The user-facing listing is never asked for retired rows (RET-1).
  expect(catalogApi.list.mock.calls.length).toBe(userListCalls)
  catalogApi.list.mock.calls.forEach(([args]) => expect(Object.keys(args)).not.toContain('status'))

  const published = await adminItemFor('Spaghetti al pomodoro')
  expect(within(published).getByText('Published')).toBeInTheDocument()
  expect(within(published).getByRole('button', { name: 'Retire' })).toHaveClass('min-h-11')
  expect(within(published).queryByRole('button', { name: 'Publish' })).not.toBeInTheDocument()

  const retired = await adminItemFor('Old stew')
  expect(within(retired).getByText('Retired')).toBeInTheDocument()
  expect(within(retired).getByRole('button', { name: 'Publish' })).toHaveClass('min-h-11')
  expect(within(retired).queryByRole('button', { name: 'Retire' })).not.toBeInTheDocument()

  // The browse grid and its selection are not mixed into the admin view.
  expect(screen.queryAllByTestId('catalog-card')).toHaveLength(0)
})

test('turning "Show retired" off returns to the browse grid', async () => {
  await renderAdmin()
  fireEvent.click(screen.getByRole('button', { name: /show retired/i }))
  await adminListing()

  fireEvent.click(screen.getByRole('button', { name: /show retired/i }))

  expect(screen.queryByRole('list', { name: 'All library entries' })).not.toBeInTheDocument()
  expect(screen.getAllByTestId('catalog-card')).toHaveLength(4)
})

test.each([
  ['Publish', 'Old stew', 9, 'publish', /published .*old stew/i],
  ['Retire', 'Spaghetti al pomodoro', 1, 'retire', /retired .*spaghetti/i],
])('%s in the admin listing calls its endpoint and refreshes both listings', async (label, title, id, method, message) => {
  catalogApi.admin[method].mockResolvedValue(adminRow({ id }))
  await renderAdmin()
  fireEvent.click(screen.getByRole('button', { name: /show retired/i }))
  const item = await adminItemFor(title)
  const userListCalls = catalogApi.list.mock.calls.length

  fireEvent.click(within(item).getByRole('button', { name: label }))

  await waitFor(() => expect(catalogApi.admin[method]).toHaveBeenCalledWith(id))
  expect(await screen.findByRole('status')).toHaveTextContent(message)
  await waitFor(() => expect(catalogApi.admin.list).toHaveBeenCalledTimes(2))
  await waitFor(() => expect(catalogApi.list.mock.calls.length).toBeGreaterThan(userListCalls))
})

test('Edit in the admin listing pre-fills from the admin row, so a retired entry is editable', async () => {
  catalogApi.admin.update.mockResolvedValue(adminRow({ id: 9 }))
  await renderAdmin()
  fireEvent.click(screen.getByRole('button', { name: /show retired/i }))
  const item = await adminItemFor('Old stew')

  fireEvent.click(within(item).getByRole('button', { name: 'Edit' }))

  expect(screen.getByLabelText('Title')).toHaveValue('Old stew')
  expect(screen.getByDisplayValue('Cook it.')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Save' }))
  await waitFor(() =>
    expect(catalogApi.admin.update).toHaveBeenCalledWith(9, expect.objectContaining({ title: 'Old stew' })),
  )
  // A retired entry is not reachable through the user-facing detail endpoint.
  expect(catalogApi.get).not.toHaveBeenCalled()
  await waitFor(() => expect(catalogApi.admin.list).toHaveBeenCalledTimes(2))
})

test('Export downloads the catalog as a JSON file through a Blob URL', async () => {
  const exported = [{ title: 'Old stew', status: 'retired' }]
  catalogApi.admin.exportCatalog.mockResolvedValue(exported)
  URL.createObjectURL = vi.fn(() => 'blob:catalog')
  URL.revokeObjectURL = vi.fn()
  const written = []
  class FakeBlob {
    constructor(parts, options) {
      written.push({ parts, type: options?.type })
    }
  }
  vi.stubGlobal('Blob', FakeBlob)
  const downloads = []
  const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function record() {
    downloads.push({ href: this.getAttribute('href'), download: this.download })
  })
  await renderAdmin()

  fireEvent.click(screen.getByRole('button', { name: /export/i }))

  await waitFor(() => expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:catalog'))
  expect(catalogApi.admin.exportCatalog).toHaveBeenCalledTimes(1)
  expect(written).toHaveLength(1)
  expect(written[0].type).toBe('application/json')
  expect(JSON.parse(written[0].parts.join(''))).toEqual(exported)
  expect(downloads).toEqual([{ href: 'blob:catalog', download: expect.stringMatching(/^catalog-export.*\.json$/) }])
  click.mockRestore()
  vi.unstubAllGlobals()
})

// --- Admin errors ------------------------------------------------------------

test('a failed save names the failure and reopens the form with what was typed', async () => {
  catalogApi.admin.create.mockRejectedValue(new Error('Unknown tag: brunch'))
  await renderAdmin()
  fireEvent.click(screen.getByRole('button', { name: /new catalog recipe/i }))

  fillAndSave({ title: 'Ribollita' })

  const alert = await screen.findByRole('alert')
  expect(alert).toHaveTextContent(/couldn.t save .*ribollita/i)
  expect(alert).toHaveTextContent('Unknown tag: brunch')
  expect(screen.getByLabelText('Title')).toHaveValue('Ribollita')

  // Saving again from the reopened form still creates rather than updates.
  catalogApi.admin.create.mockResolvedValue(adminRow({ id: 30 }))
  fireEvent.click(screen.getByRole('button', { name: 'Save' }))
  await waitFor(() => expect(catalogApi.admin.create).toHaveBeenCalledTimes(2))
  expect(catalogApi.admin.update).not.toHaveBeenCalled()
})

test.each([
  ['the admin listing', 'list', async () => {
    fireEvent.click(screen.getByRole('button', { name: /show retired/i }))
  }, /couldn.t load .*retired/i],
  ['an export', 'exportCatalog', async () => {
    fireEvent.click(screen.getByRole('button', { name: /export/i }))
  }, /couldn.t export/i],
  ['a retire', 'retire', async () => {
    catalogApi.admin.list.mockResolvedValue(ADMIN_ROWS)
    fireEvent.click(screen.getByRole('button', { name: /show retired/i }))
    fireEvent.click(within(await adminItemFor('Spaghetti al pomodoro')).getByRole('button', { name: 'Retire' }))
  }, /couldn.t retire .*spaghetti/i],
  ['a publish', 'publish', async () => {
    catalogApi.admin.list.mockResolvedValue(ADMIN_ROWS)
    fireEvent.click(screen.getByRole('button', { name: /show retired/i }))
    fireEvent.click(within(await adminItemFor('Old stew')).getByRole('button', { name: 'Publish' }))
  }, /couldn.t publish .*old stew/i],
])('a failed %s shows an alert naming it', async (_label, method, act, message) => {
  await renderAdmin()
  catalogApi.admin[method].mockRejectedValue(new Error('Forbidden'))

  await act()

  const alert = await screen.findByRole('alert')
  expect(alert).toHaveTextContent(message)
  expect(alert).toHaveTextContent('Forbidden')
})

test('there is no hard-delete control anywhere in the admin UI (RET-5)', async () => {
  catalogApi.get.mockResolvedValue({ ...ROWS[1], procedure: 'Roast for an hour.' })
  await renderAdmin()
  expect(screen.queryAllByRole('button', { name: /delete/i })).toHaveLength(0)

  fireEvent.click(screen.getByRole('button', { name: /Roast chicken/ }))
  await screen.findByText('Roast for an hour.')
  expect(screen.queryAllByRole('button', { name: /delete/i })).toHaveLength(0)
  fireEvent.click(screen.getByRole('button', { name: 'Close' }))

  fireEvent.click(screen.getByRole('button', { name: /show retired/i }))
  await adminListing()
  expect(screen.queryAllByRole('button', { name: /delete/i })).toHaveLength(0)
})
