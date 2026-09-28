/**
 * @vitest-environment jsdom
 */
import { render, screen, fireEvent, waitFor, within, cleanup } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import '@testing-library/jest-dom/vitest'
import CatalogImportPage from '../CatalogImportPage'
import { catalogApi } from '../../api/catalogApi'
import { stubViewport } from '../../test/stubViewport'

// The mappers and error helpers stay real; only the network calls are mocked.
vi.mock('../../api/catalogApi', async (importOriginal) => ({
  ...(await importOriginal()),
  catalogApi: {
    imports: {
      create: vi.fn(),
      open: vi.fn(),
      get: vi.fn(),
      remove: vi.fn(),
    },
  },
}))

function item(overrides) {
  return {
    id: 1,
    position: 0,
    title: 'Ribollita',
    state: 'pending',
    error: null,
    problems: [],
    duplicate_recipe_id: null,
    committed_recipe_id: null,
    ...overrides,
  }
}

const BATCH = {
  id: 7,
  filename: 'autumn.json',
  created_at: '2026-09-20T09:00:00Z',
  created_by_user_id: 3,
  counts: { pending: 2, invalid: 1, skipped: 1, committed: 1 },
  items: [
    item({ id: 1, position: 0, title: 'Ribollita' }),
    item({ id: 2, position: 1, title: 'Pasta e fagioli', problems: ['Unknown ingredient: borlotti'] }),
    item({ id: 3, position: 2, title: 'Broken entry', state: 'invalid', error: 'servings must be at least 1' }),
    item({ id: 4, position: 3, title: 'Old stew', state: 'skipped', duplicate_recipe_id: 41 }),
    item({ id: 5, position: 4, title: 'Minestrone', state: 'committed', committed_recipe_id: 90 }),
  ],
}

// A `File` whose `text()` resolves to `contents` -- jsdom's File has no text().
function jsonFile(name, contents) {
  return { name, text: () => Promise.resolve(contents) }
}

function chooseFile(file) {
  const input = screen.getByLabelText('Choose a recipe file')
  Object.defineProperty(input, 'files', { value: [file], configurable: true })
  fireEvent.change(input)
}

const listing = () => screen.findByRole('list', { name: 'Recipes in this file' })
const rowFor = async (title) => within(await listing()).getByText(title).closest('li')

async function renderWithBatch() {
  catalogApi.imports.open.mockResolvedValue(BATCH)
  render(
    <MemoryRouter>
      <CatalogImportPage />
    </MemoryRouter>,
  )
  await screen.findByText('Ribollita')
}

async function renderEmpty() {
  catalogApi.imports.open.mockResolvedValue(null)
  render(
    <MemoryRouter>
      <CatalogImportPage />
    </MemoryRouter>,
  )
  await screen.findByLabelText('Choose a recipe file')
}

beforeEach(() => {
  // The dish-glyph Icon fetches SVGs from a CDN; keep tests hermetic.
  globalThis.fetch = vi.fn(() => Promise.reject(new Error('no network')))
  stubViewport(false)
  catalogApi.imports.open.mockResolvedValue(null)
})

afterEach(() => {
  vi.clearAllMocks()
  cleanup()
})

// --- Upload ------------------------------------------------------------------

test('with nothing staged the page offers a file and no item list', async () => {
  await renderEmpty()

  expect(catalogApi.imports.open).toHaveBeenCalledTimes(1)
  expect(screen.queryByRole('list', { name: 'Recipes in this file' })).not.toBeInTheDocument()
  expect(screen.getByRole('button', { name: /upload/i })).toBeDisabled()
})

test('a chosen file is read and counted before anything is sent', async () => {
  await renderEmpty()

  chooseFile(jsonFile('autumn.json', JSON.stringify([{ title: 'Ribollita' }, { title: 'Minestrone' }])))

  expect(await screen.findByText(/2 recipes/i)).toBeInTheDocument()
  expect(screen.getByRole('button', { name: /upload/i })).toBeEnabled()
  expect(catalogApi.imports.create).not.toHaveBeenCalled()
})

test('a file that is not JSON is named as unreadable and never uploaded', async () => {
  await renderEmpty()

  chooseFile(jsonFile('notes.txt', 'this is not json'))

  expect(await screen.findByRole('alert')).toHaveTextContent(/couldn.t read .*notes\.txt/i)
  expect(screen.getByRole('button', { name: /upload/i })).toBeDisabled()
  expect(catalogApi.imports.create).not.toHaveBeenCalled()
})

test('valid JSON that is not a list of recipes is refused', async () => {
  await renderEmpty()

  chooseFile(jsonFile('one.json', JSON.stringify({ title: 'Ribollita' })))

  expect(await screen.findByRole('alert')).toHaveTextContent(/list of recipes/i)
  expect(catalogApi.imports.create).not.toHaveBeenCalled()
})

test('an empty list is refused rather than staged', async () => {
  await renderEmpty()

  chooseFile(jsonFile('empty.json', '[]'))

  expect(await screen.findByRole('alert')).toHaveTextContent(/no recipes/i)
  expect(screen.getByRole('button', { name: /upload/i })).toBeDisabled()
})

test('uploading sends the filename and the parsed entries, then shows the batch', async () => {
  const entries = [{ title: 'Ribollita' }]
  catalogApi.imports.create.mockResolvedValue(BATCH)
  await renderEmpty()
  chooseFile(jsonFile('autumn.json', JSON.stringify(entries)))
  await screen.findByText(/1 recipe/i)

  fireEvent.click(screen.getByRole('button', { name: /upload/i }))

  await waitFor(() => expect(catalogApi.imports.create).toHaveBeenCalledWith('autumn.json', entries))
  expect(await screen.findByText('Ribollita')).toBeInTheDocument()
})

test('a failed upload says so and keeps the chosen file', async () => {
  catalogApi.imports.create.mockRejectedValue(new Error('A batch is already open'))
  await renderEmpty()
  chooseFile(jsonFile('autumn.json', JSON.stringify([{ title: 'Ribollita' }])))
  await screen.findByText(/1 recipe/i)

  fireEvent.click(screen.getByRole('button', { name: /upload/i }))

  const alert = await screen.findByRole('alert')
  expect(alert).toHaveTextContent(/couldn.t upload .*autumn\.json/i)
  expect(alert).toHaveTextContent('A batch is already open')
  expect(screen.getByRole('button', { name: /upload/i })).toBeEnabled()
})

// --- Resuming an open batch ---------------------------------------------------

test('an open batch is shown on load, not silently discarded', async () => {
  await renderWithBatch()

  expect(screen.getByText('autumn.json')).toBeInTheDocument()
  expect(screen.queryByLabelText('Choose a recipe file')).not.toBeInTheDocument()
  expect(catalogApi.imports.create).not.toHaveBeenCalled()
})

test('progress counts what is left against the whole file', async () => {
  await renderWithBatch()

  expect(screen.getByText(/2 of 5 reviewed/i)).toBeInTheDocument()
  expect(screen.getByText(/3 left/i)).toBeInTheDocument()
})

test('each item carries its state, and an invalid one carries its reason', async () => {
  await renderWithBatch()

  expect(within(await rowFor('Ribollita')).getByText('To review')).toBeInTheDocument()

  const broken = await rowFor('Broken entry')
  expect(within(broken).getByText('Invalid')).toBeInTheDocument()
  expect(within(broken).getByText(/servings must be at least 1/)).toBeInTheDocument()

  expect(within(await rowFor('Old stew')).getByText('Skipped')).toBeInTheDocument()
  expect(within(await rowFor('Minestrone')).getByText('Committed')).toBeInTheDocument()
})

test('a title the library already has is flagged as a duplicate', async () => {
  await renderWithBatch()

  expect(within(await rowFor('Old stew')).getByText('Duplicate')).toBeInTheDocument()
  expect(within(await rowFor('Ribollita')).queryByText('Duplicate')).not.toBeInTheDocument()
})

test('an item whose names do not resolve yet says what is unresolved', async () => {
  await renderWithBatch()

  expect(within(await rowFor('Pasta e fagioli')).getByText(/Unknown ingredient: borlotti/)).toBeInTheDocument()
})

test('items still to review link to the review page; settled ones do not', async () => {
  await renderWithBatch()

  const link = within(await rowFor('Ribollita')).getByRole('link', { name: /review/i })
  expect(link).toHaveAttribute('href', '/discover/import/7')
  expect(within(await rowFor('Broken entry')).getByRole('link', { name: /review/i })).toBeInTheDocument()
  expect(within(await rowFor('Old stew')).queryByRole('link')).not.toBeInTheDocument()
  expect(within(await rowFor('Minestrone')).queryByRole('link')).not.toBeInTheDocument()
})

// --- Abandoning ---------------------------------------------------------------

test('abandoning asks first, and cancelling leaves the batch alone', async () => {
  await renderWithBatch()

  fireEvent.click(screen.getByRole('button', { name: /abandon/i }))
  expect(await screen.findByRole('dialog')).toHaveAccessibleName(/discard autumn\.json/i)

  fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))

  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  expect(catalogApi.imports.remove).not.toHaveBeenCalled()
  expect(screen.getByText('Ribollita')).toBeInTheDocument()
})

test('confirming the discard deletes the batch and offers a fresh file', async () => {
  catalogApi.imports.remove.mockResolvedValue(null)
  await renderWithBatch()

  fireEvent.click(screen.getByRole('button', { name: /abandon/i }))
  fireEvent.click(await screen.findByRole('button', { name: /discard/i }))

  await waitFor(() => expect(catalogApi.imports.remove).toHaveBeenCalledWith(7))
  expect(await screen.findByLabelText('Choose a recipe file')).toBeInTheDocument()
  expect(screen.queryByText('Ribollita')).not.toBeInTheDocument()
})

test('a failed discard says so and keeps the batch on screen', async () => {
  catalogApi.imports.remove.mockRejectedValue(new Error('Forbidden'))
  await renderWithBatch()

  fireEvent.click(screen.getByRole('button', { name: /abandon/i }))
  fireEvent.click(await screen.findByRole('button', { name: /discard/i }))

  const alert = await screen.findByRole('alert')
  expect(alert).toHaveTextContent(/couldn.t discard/i)
  expect(alert).toHaveTextContent('Forbidden')
  expect(screen.getByText('Ribollita')).toBeInTheDocument()
})

// --- Failures and mobile -------------------------------------------------------

test('a failed load shows an error with a retry', async () => {
  catalogApi.imports.open.mockRejectedValueOnce(new Error('Forbidden'))
  render(
    <MemoryRouter>
      <CatalogImportPage />
    </MemoryRouter>,
  )

  expect(await screen.findByRole('alert')).toHaveTextContent(/couldn.t load the import/i)

  catalogApi.imports.open.mockResolvedValue(BATCH)
  fireEvent.click(screen.getByRole('button', { name: /try again/i }))

  expect(await screen.findByText('Ribollita')).toBeInTheDocument()
})

test('on a phone the batch controls keep 44px tap targets', async () => {
  stubViewport(true)
  await renderWithBatch()

  expect(screen.getByRole('button', { name: /abandon/i })).toHaveClass('min-h-11')
})
