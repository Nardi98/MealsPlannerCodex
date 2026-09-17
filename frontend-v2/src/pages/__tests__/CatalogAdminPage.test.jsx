/**
 * @vitest-environment jsdom
 */
import { render, screen, fireEvent, waitFor, within, cleanup } from '@testing-library/react'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import '@testing-library/jest-dom/vitest'
import CatalogAdminPage from '../CatalogAdminPage'
import { catalogApi } from '../../api/catalogApi'
import { tagsApi } from '../../api/tagsApi'
import { ingredientsApi } from '../../api/ingredientsApi'
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

vi.mock('../../api/tagsApi', () => ({ tagsApi: { fetchAll: vi.fn() } }))
vi.mock('../../api/ingredientsApi', () => ({ ingredientsApi: { fetchAll: vi.fn() } }))

// AdminRow = CatalogRow − in_my_book + {procedure, status, published_at, retired_at}.
function adminRow(overrides) {
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
    procedure: 'Cook it.',
    status: 'published',
    published_at: '2026-09-01T10:00:00Z',
    retired_at: null,
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

// The most recent `admin.list` call's argument.
const lastListArgs = () => catalogApi.admin.list.mock.calls.at(-1)[0]

const listing = () => screen.findByRole('list', { name: 'All library entries' })
const itemFor = async (title) => within(await listing()).getByText(title).closest('li')

async function renderLoaded() {
  render(<CatalogAdminPage />)
  await screen.findByText('Spaghetti al pomodoro')
}

// Fills the fields a catalog recipe needs and saves the open form.
function fillAndSave({ title }) {
  fireEvent.change(screen.getByLabelText('Title'), { target: { value: title } })
  fireEvent.change(screen.getByLabelText('Course'), { target: { value: 'main' } })
  fireEvent.click(screen.getByRole('button', { name: 'Save' }))
}

// Types into the ingredient row at `idx` (rows past the first are added first).
function fillIngredient(idx, { name, amount }) {
  if (idx > 0) fireEvent.click(screen.getByRole('button', { name: '+ Add ingredient' }))
  fireEvent.change(screen.getAllByPlaceholderText('ingredient')[idx], { target: { value: name } })
  fireEvent.change(screen.getAllByPlaceholderText('amt')[idx], { target: { value: amount } })
}

// The Error `client.request` throws: the message, plus the parsed body on `data`.
function httpError(status, body) {
  const message = typeof body.detail === 'string' ? body.detail : JSON.stringify(body)
  return Object.assign(new Error(message), { status, data: body })
}

beforeEach(() => {
  vi.useRealTimers()
  // The dish-glyph Icon fetches SVGs from a CDN; keep tests hermetic.
  globalThis.fetch = vi.fn(() => Promise.reject(new Error('no network')))
  stubViewport(false)
  catalogApi.admin.list.mockResolvedValue(ADMIN_ROWS)
  catalogApi.admin.ingredients.mockResolvedValue([])
  catalogApi.admin.tags.mockResolvedValue([])
  tagsApi.fetchAll.mockResolvedValue([])
  ingredientsApi.fetchAll.mockResolvedValue([])
})

afterEach(() => {
  vi.clearAllMocks()
  cleanup()
})

// --- Listing ----------------------------------------------------------------

test('lists every entry with its status and count, published and retired alike', async () => {
  await renderLoaded()

  const published = await itemFor('Spaghetti al pomodoro')
  expect(within(published).getByText('Published')).toBeInTheDocument()
  expect(within(published).getByRole('button', { name: 'Retire' })).toHaveClass('min-h-11')
  expect(within(published).queryByRole('button', { name: 'Publish' })).not.toBeInTheDocument()

  const retired = await itemFor('Old stew')
  expect(within(retired).getByText('Retired')).toBeInTheDocument()
  expect(within(retired).getByRole('button', { name: 'Publish' })).toHaveClass('min-h-11')
  expect(within(retired).queryByRole('button', { name: 'Retire' })).not.toBeInTheDocument()
})

test('curating is not browsing: no cards, no selection, no adopting', async () => {
  await renderLoaded()

  expect(screen.queryAllByTestId('catalog-card')).toHaveLength(0)
  expect(screen.queryAllByRole('checkbox')).toHaveLength(0)
  expect(screen.queryByRole('button', { name: /add \d+ recipe/i })).not.toBeInTheDocument()
  expect(catalogApi.list).not.toHaveBeenCalled()
  expect(catalogApi.adopt).not.toHaveBeenCalled()
})

test('offers new and export, and never a hard delete (RET-5)', async () => {
  await renderLoaded()

  expect(screen.getByRole('button', { name: /new catalog recipe/i })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: /export/i })).toBeInTheDocument()
  expect(screen.queryAllByRole('button', { name: /delete/i })).toHaveLength(0)
  // "Show retired" is gone: the status filter does that job now.
  expect(screen.queryByRole('button', { name: /show retired/i })).not.toBeInTheDocument()
})

test('on a phone the toolbar keeps 44px tap targets', async () => {
  stubViewport(true)
  await renderLoaded()

  for (const name of [/new catalog recipe/i, /export/i]) {
    expect(screen.getByRole('button', { name })).toHaveClass('min-h-11')
  }
})

test('an empty library says so instead of rendering a blank page', async () => {
  catalogApi.admin.list.mockResolvedValue([])
  render(<CatalogAdminPage />)

  expect(await screen.findByText(/no entries yet/i)).toBeInTheDocument()
})

// --- Search, status and sort (all server-side) -------------------------------

test('the first request asks for everything, by title', async () => {
  await renderLoaded()

  expect(catalogApi.admin.list).toHaveBeenCalledTimes(1)
  expect(lastListArgs()).toEqual({ q: '', status: '', sort: 'title' })
})

test('search is debounced: only the settled text is sent as q', async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true })
  await renderLoaded()
  const box = screen.getByLabelText('Search the library')

  fireEvent.change(box, { target: { value: 'ste' } })
  fireEvent.change(box, { target: { value: 'stew' } })
  await vi.advanceTimersByTimeAsync(400)

  await waitFor(() => expect(lastListArgs()).toMatchObject({ q: 'stew' }))
  expect(catalogApi.admin.list).toHaveBeenCalledTimes(2)
})

test('the status filter refetches for that status alone', async () => {
  await renderLoaded()

  fireEvent.change(screen.getByLabelText('Filter by status'), { target: { value: 'retired' } })

  await waitFor(() => expect(lastListArgs()).toMatchObject({ status: 'retired' }))
})

test('the status filter offers all three states', async () => {
  await renderLoaded()

  const values = within(screen.getByLabelText('Filter by status'))
    .getAllByRole('option')
    .map((o) => o.value)
  expect(values).toEqual(['', 'published', 'retired'])
})

test('changing the sort refetches by popularity', async () => {
  await renderLoaded()

  fireEvent.change(screen.getByLabelText('Sort recipes'), { target: { value: 'popular' } })

  await waitFor(() => expect(lastListArgs()).toMatchObject({ sort: 'popular' }))
})

// --- Authoring ---------------------------------------------------------------

test('"New catalog recipe" opens the form on the library sources, with no pantry writes', async () => {
  catalogApi.admin.ingredients.mockResolvedValue([
    { id: 50, name: 'Cavolo nero', season_months: [], grams_per_ml: null, grams_per_piece: null, preferred_dimension: null },
  ])
  catalogApi.admin.tags.mockResolvedValue([{ id: 60, name: 'soup' }])
  await renderLoaded()

  fireEvent.click(screen.getByRole('button', { name: /new catalog recipe/i }))

  expect(screen.getByRole('heading', { name: 'New catalog recipe' })).toBeInTheDocument()
  await waitFor(() => expect(catalogApi.admin.ingredients).toHaveBeenCalled())
  expect(catalogApi.admin.tags).toHaveBeenCalled()
  expect(ingredientsApi.fetchAll).not.toHaveBeenCalled()
  expect(tagsApi.fetchAll).not.toHaveBeenCalled()
  fireEvent.focus(screen.getByPlaceholderText('ingredient'))
  expect(await screen.findByText('Cavolo nero')).toBeInTheDocument()
  expect(screen.queryByText(/add new ingredient/i)).not.toBeInTheDocument()
})

test('the catalog form offers library tags only, never a free-text new tag', async () => {
  catalogApi.admin.tags.mockResolvedValue([{ id: 60, name: 'soup' }])
  await renderLoaded()
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
  await renderLoaded()
  fireEvent.click(screen.getByRole('button', { name: /new catalog recipe/i }))

  fillAndSave({ title: 'Ribollita' })

  await waitFor(() => expect(catalogApi.admin.create).toHaveBeenCalledTimes(1))
  expect(catalogApi.admin.create).toHaveBeenCalledWith(
    expect.objectContaining({ title: 'Ribollita', course: 'main', servings: 1 }),
  )
  expect(await screen.findByRole('status')).toHaveTextContent(/saved .*ribollita/i)
  await waitFor(() => expect(catalogApi.admin.list).toHaveBeenCalledTimes(2))
  expect(catalogApi.admin.update).not.toHaveBeenCalled()
})

test('Edit pre-fills from the admin row, so a retired entry is editable', async () => {
  catalogApi.admin.update.mockResolvedValue(adminRow({ id: 9 }))
  await renderLoaded()
  const item = await itemFor('Old stew')

  fireEvent.click(within(item).getByRole('button', { name: 'Edit' }))

  expect(screen.getByRole('heading', { name: 'Edit catalog recipe' })).toBeInTheDocument()
  expect(screen.getByLabelText('Title')).toHaveValue('Old stew')
  expect(screen.getByDisplayValue('Cook it.')).toBeInTheDocument()
  expect(screen.getByPlaceholderText('ingredient')).toHaveValue('Pasta')

  fireEvent.click(screen.getByRole('button', { name: 'Save' }))

  await waitFor(() =>
    expect(catalogApi.admin.update).toHaveBeenCalledWith(9, expect.objectContaining({ title: 'Old stew' })),
  )
  // A retired entry is not reachable through the user-facing detail endpoint.
  expect(catalogApi.get).not.toHaveBeenCalled()
  await waitFor(() => expect(catalogApi.admin.list).toHaveBeenCalledTimes(2))
})

test.each([
  ['Publish', 'Old stew', 9, 'publish', /published .*old stew/i],
  ['Retire', 'Spaghetti al pomodoro', 1, 'retire', /retired .*spaghetti/i],
])('%s calls its endpoint and refreshes the listing', async (label, title, id, method, message) => {
  catalogApi.admin[method].mockResolvedValue(adminRow({ id }))
  await renderLoaded()
  const item = await itemFor(title)

  fireEvent.click(within(item).getByRole('button', { name: label }))

  await waitFor(() => expect(catalogApi.admin[method]).toHaveBeenCalledWith(id))
  expect(await screen.findByRole('status')).toHaveTextContent(message)
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
  await renderLoaded()

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

// --- Errors -------------------------------------------------------------------

test('a failed load shows an error with a retry', async () => {
  catalogApi.admin.list.mockRejectedValueOnce(new Error('Forbidden'))
  render(<CatalogAdminPage />)

  expect(await screen.findByRole('alert')).toHaveTextContent(/couldn.t load the library/i)

  catalogApi.admin.list.mockResolvedValue(ADMIN_ROWS)
  fireEvent.click(screen.getByRole('button', { name: /try again/i }))

  expect(await screen.findByText('Old stew')).toBeInTheDocument()
})

test('an ingredient without an amount is caught before any request, naming the ingredient', async () => {
  await renderLoaded()
  fireEvent.click(screen.getByRole('button', { name: /new catalog recipe/i }))
  fireEvent.change(screen.getByLabelText('Title'), { target: { value: 'Ribollita' } })
  fireEvent.change(screen.getByLabelText('Course'), { target: { value: 'main' } })
  fillIngredient(0, { name: 'Cavolo nero', amount: '800' })
  fillIngredient(1, { name: 'Olive oil', amount: '' })

  fireEvent.click(screen.getByRole('button', { name: 'Save' }))

  const alert = await screen.findByRole('alert')
  expect(alert).toHaveTextContent('Couldn\'t save “Ribollita”: "Olive oil" needs an amount and a unit.')
  expect(catalogApi.admin.create).not.toHaveBeenCalled()
  expect(screen.getByLabelText('Title')).toHaveValue('Ribollita')
  expect(screen.getAllByPlaceholderText('ingredient').map((i) => i.value)).toEqual(['Cavolo nero', 'Olive oil'])
})

test('a duplicate ingredient is caught before any request, with the server wording', async () => {
  await renderLoaded()
  fireEvent.click(screen.getByRole('button', { name: /new catalog recipe/i }))
  fireEvent.change(screen.getByLabelText('Title'), { target: { value: 'Ribollita' } })
  fireEvent.change(screen.getByLabelText('Course'), { target: { value: 'main' } })
  fillIngredient(0, { name: 'Basil', amount: '5' })
  fillIngredient(1, { name: 'Basil', amount: '10' })

  fireEvent.click(screen.getByRole('button', { name: 'Save' }))

  expect(await screen.findByRole('alert')).toHaveTextContent('Duplicate ingredient: Basil')
  expect(catalogApi.admin.create).not.toHaveBeenCalled()
})

test('a 422 from the server reads as sentences, not raw JSON', async () => {
  catalogApi.admin.create.mockRejectedValue(
    httpError(422, {
      detail: [{ loc: ['body', 'servings'], msg: 'Input should be greater than or equal to 1', type: 'greater_than_equal' }],
    }),
  )
  await renderLoaded()
  fireEvent.click(screen.getByRole('button', { name: /new catalog recipe/i }))

  fillAndSave({ title: 'Ribollita' })

  const alert = await screen.findByRole('alert')
  expect(alert).toHaveTextContent('servings: Input should be greater than or equal to 1')
  expect(alert.textContent).not.toMatch(/[{}[\]]|"loc"|greater_than_equal/)
})

test('a failed save names the failure and reopens the form with what was typed', async () => {
  catalogApi.admin.create.mockRejectedValue(httpError(400, { detail: 'Unknown tag: brunch' }))
  await renderLoaded()
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
  ['an export', 'exportCatalog', async () => {
    fireEvent.click(screen.getByRole('button', { name: /export/i }))
  }, /couldn.t export/i],
  ['a retire', 'retire', async () => {
    fireEvent.click(within(await itemFor('Spaghetti al pomodoro')).getByRole('button', { name: 'Retire' }))
  }, /couldn.t retire .*spaghetti/i],
  ['a publish', 'publish', async () => {
    fireEvent.click(within(await itemFor('Old stew')).getByRole('button', { name: 'Publish' }))
  }, /couldn.t publish .*old stew/i],
])('a failed %s shows an alert naming it', async (_label, method, act, message) => {
  await renderLoaded()
  catalogApi.admin[method].mockRejectedValue(new Error('Forbidden'))

  await act()

  const alert = await screen.findByRole('alert')
  expect(alert).toHaveTextContent(message)
  expect(alert).toHaveTextContent('Forbidden')
})
