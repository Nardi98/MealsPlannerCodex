/**
 * @vitest-environment jsdom
 */
import { render, screen, fireEvent, waitFor, within, cleanup } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import '@testing-library/jest-dom/vitest'
import CatalogImportReviewPage from '../CatalogImportReviewPage'
import { catalogApi } from '../../api/catalogApi'
import { recipesApi } from '../../api/recipesApi'
import { stubViewport } from '../../test/stubViewport'

// The real mappers stay real; only the network calls are mocked.
vi.mock('../../api/catalogApi', async (importOriginal) => ({
  ...(await importOriginal()),
  catalogApi: {
    admin: { ingredients: vi.fn(), tags: vi.fn(), createIngredient: vi.fn() },
    imports: {
      get: vi.fn(),
      item: vi.fn(),
      saveItem: vi.fn(),
      skipItem: vi.fn(),
      commitItem: vi.fn(),
    },
  },
}))

vi.mock('../../api/recipesApi', () => ({ recipesApi: { uploadImage: vi.fn() } }))

const BATCH_ID = 7

// An ItemSummary and nothing more: passing a detail in keeps only these keys,
// exactly as the batch overview answers.
function summary(overrides = {}) {
  const row = {
    id: 11,
    position: 0,
    title: 'Pasta al forno',
    state: 'pending',
    error: null,
    problems: [],
    duplicate_recipe_id: null,
    committed_recipe_id: null,
  }
  for (const key of Object.keys(row)) if (key in overrides) row[key] = overrides[key]
  return row
}

function detail(overrides) {
  const base = summary(overrides)
  return {
    ...base,
    source: {},
    draft: {
      title: 'Pasta al forno',
      course: 'first-course',
      servings: 4,
      bulk_prep: false,
      procedure: 'Bake it.',
      image_url: null,
      tags: ['pasta'],
      ingredients: [{ name: 'Pasta', quantity: 320, unit: 'g', ingredient_id: 3 }],
    },
    duplicate: null,
    ...overrides,
  }
}

const UNRESOLVED = detail({
  id: 11,
  problems: ['Unknown ingredient: tomatoe'],
  draft: {
    title: 'Pasta al forno',
    course: 'first-course',
    servings: 4,
    bulk_prep: false,
    procedure: 'Bake it.',
    image_url: null,
    tags: ['pasta'],
    ingredients: [
      { name: 'Pasta', quantity: 320, unit: 'g', ingredient_id: 3 },
      { name: 'tomatoe', quantity: 2, unit: 'piece', ingredient_id: null },
    ],
  },
})

const DUPLICATE_ITEM = detail({
  id: 12,
  position: 1,
  title: 'Minestrone',
  duplicate_recipe_id: 90,
  draft: {
    title: 'Minestrone',
    course: 'first-course',
    servings: 2,
    bulk_prep: true,
    procedure: 'Simmer for an hour.',
    image_url: null,
    tags: ['soup'],
    ingredients: [{ name: 'Carrot', quantity: 2, unit: 'piece', ingredient_id: 5 }],
  },
  duplicate: {
    id: 90,
    title: 'Minestrone',
    course: 'first-course',
    servings: 6,
    bulk_prep: false,
    image_url: null,
    procedure: 'Simmer for two hours.',
    tags: ['soup', 'winter'],
    ingredients: [{ name: 'Carrot', quantity: 4, unit: 'piece' }],
  },
})

function batch(items) {
  return {
    id: BATCH_ID,
    filename: 'pack.json',
    created_at: '2026-09-01T10:00:00Z',
    created_by_user_id: 1,
    counts: { pending: items.length },
    // The overview lists summaries: a detail minus what only the review needs.
    items: items.map((item) => summary(item)),
  }
}

const SYSTEM_INGREDIENTS = [
  { id: 3, name: 'Pasta', season_months: [], categories: [], grams_per_ml: null, grams_per_piece: null, preferred_dimension: 'mass' },
  { id: 5, name: 'Carrot', season_months: [], categories: [], grams_per_ml: null, grams_per_piece: null, preferred_dimension: 'piece' },
  { id: 8, name: 'Tomato paste', season_months: [], categories: [], grams_per_ml: null, grams_per_piece: null, preferred_dimension: 'mass' },
]

function renderPage() {
  return render(
    <MemoryRouter initialEntries={[`/discover/import/${BATCH_ID}`]}>
      <Routes>
        <Route path="/discover/import/:batchId" element={<CatalogImportReviewPage />} />
        <Route path="/discover/import" element={<div>Import overview</div>} />
      </Routes>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  globalThis.fetch = vi.fn(() => Promise.reject(new Error('no network')))
  stubViewport(false)
  catalogApi.admin.ingredients.mockResolvedValue(SYSTEM_INGREDIENTS)
  catalogApi.admin.tags.mockResolvedValue([{ id: 1, name: 'pasta' }, { id: 2, name: 'soup' }])
  catalogApi.imports.get.mockResolvedValue(batch([UNRESOLVED, DUPLICATE_ITEM]))
  catalogApi.imports.item.mockImplementation((_batchId, itemId) =>
    Promise.resolve(itemId === 12 ? DUPLICATE_ITEM : UNRESOLVED),
  )
})

afterEach(() => {
  vi.clearAllMocks()
  cleanup()
})

// --- Side by side -----------------------------------------------------------

test('shows the existing catalog entry beside the incoming one when they collide', async () => {
  catalogApi.imports.get.mockResolvedValue(batch([DUPLICATE_ITEM]))
  catalogApi.imports.item.mockResolvedValue(DUPLICATE_ITEM)
  renderPage()

  const incoming = await screen.findByRole('region', { name: 'Incoming recipe' })
  expect(within(incoming).getByLabelText('Title')).toHaveValue('Minestrone')

  const existing = screen.getByRole('region', { name: 'Already in the catalog' })
  expect(within(existing).getByText('Simmer for two hours.')).toBeInTheDocument()
  expect(within(existing).getByText(/4 piece Carrot/)).toBeInTheDocument()
})

// --- Resolving ingredients --------------------------------------------------

test('resolves an unknown line onto an existing system ingredient', async () => {
  catalogApi.imports.saveItem.mockResolvedValue(detail({ id: 11, problems: [] }))
  renderPage()
  await screen.findByRole('region', { name: 'Incoming recipe' })

  expect(screen.getByText('Unknown ingredient: tomatoe')).toBeInTheDocument()

  const inputs = screen.getAllByPlaceholderText('ingredient')
  fireEvent.change(inputs[1], { target: { value: 'tomato' } })
  fireEvent.mouseDown(screen.getByText('Tomato paste'))
  fireEvent.click(screen.getByRole('button', { name: 'Save draft' }))

  await waitFor(() => expect(catalogApi.imports.saveItem).toHaveBeenCalled())
  const [, , saved] = catalogApi.imports.saveItem.mock.calls.at(-1)
  expect(saved.ingredients[1]).toEqual({
    name: 'Tomato paste',
    quantity: 2,
    unit: 'piece',
    ingredient_id: 8,
  })
})

test('creates a system ingredient from the page and resolves the line onto it', async () => {
  catalogApi.admin.createIngredient.mockResolvedValue({ id: 42, name: 'Tomatoes' })
  catalogApi.imports.saveItem.mockResolvedValue(detail({ id: 11, problems: [] }))
  renderPage()
  await screen.findByRole('region', { name: 'Incoming recipe' })

  const inputs = screen.getAllByPlaceholderText('ingredient')
  fireEvent.focus(inputs[1])
  fireEvent.mouseDown(screen.getByText('+ Add new ingredient'))

  const form = await screen.findByRole('heading', { name: 'New system ingredient' })
  expect(form).toBeInTheDocument()
  fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'Tomatoes' } })
  fireEvent.click(screen.getByRole('button', { name: 'Create and use' }))

  await waitFor(() => expect(catalogApi.admin.createIngredient).toHaveBeenCalled())
  expect(catalogApi.admin.createIngredient.mock.calls.at(-1)[0]).toMatchObject({ name: 'Tomatoes' })

  await waitFor(() =>
    expect(screen.queryByRole('heading', { name: 'New system ingredient' })).not.toBeInTheDocument(),
  )
  fireEvent.click(screen.getByRole('button', { name: 'Save draft' }))
  await waitFor(() => expect(catalogApi.imports.saveItem).toHaveBeenCalled())
  expect(catalogApi.imports.saveItem.mock.calls.at(-1)[2].ingredients[1]).toEqual({
    name: 'Tomatoes',
    quantity: 2,
    unit: 'piece',
    ingredient_id: 42,
  })
})

// --- Editing the incoming recipe -------------------------------------------

test('saves the fields the file got wrong, tags included', async () => {
  catalogApi.imports.saveItem.mockResolvedValue(UNRESOLVED)
  renderPage()
  await screen.findByRole('region', { name: 'Incoming recipe' })

  fireEvent.change(screen.getByLabelText('Servings'), { target: { value: '6' } })
  fireEvent.change(screen.getByLabelText('Procedure'), { target: { value: 'Bake for an hour.' } })
  fireEvent.click(screen.getByLabelText('Bulk prep'))
  fireEvent.click(screen.getByRole('button', { name: 'Remove tag pasta' }))
  fireEvent.change(screen.getByLabelText('Add a tag'), { target: { value: 'winter' } })
  fireEvent.click(screen.getByRole('button', { name: 'Add tag' }))
  fireEvent.click(screen.getByRole('button', { name: 'Save draft' }))

  await waitFor(() => expect(catalogApi.imports.saveItem).toHaveBeenCalled())
  expect(catalogApi.imports.saveItem.mock.calls.at(-1)[2]).toMatchObject({
    servings: 6,
    procedure: 'Bake for an hour.',
    bulk_prep: true,
    tags: ['winter'],
  })
})

test('shows why the file left an entry unusable', async () => {
  const broken = detail({ id: 11, state: 'invalid', error: 'servings must be a positive integer' })
  catalogApi.imports.get.mockResolvedValue(batch([broken]))
  catalogApi.imports.item.mockResolvedValue(broken)
  renderPage()

  expect(await screen.findByRole('alert')).toHaveTextContent('servings must be a positive integer')
})

// --- Footer actions ---------------------------------------------------------

test('refuses to commit while a name is unresolved, and says which', async () => {
  renderPage()
  await screen.findByRole('region', { name: 'Incoming recipe' })

  expect(screen.getByRole('button', { name: 'Commit as draft' })).toBeDisabled()
  expect(screen.getByText(/Can't commit yet: Unknown ingredient: tomatoe/)).toBeInTheDocument()
})

test('commits an item that resolves, and moves to the next one', async () => {
  catalogApi.imports.get.mockResolvedValue(batch([detail({ id: 11, problems: [] }), DUPLICATE_ITEM]))
  catalogApi.imports.item.mockImplementation((_batchId, itemId) =>
    Promise.resolve(itemId === 12 ? DUPLICATE_ITEM : detail({ id: 11, problems: [] })),
  )
  catalogApi.imports.commitItem.mockResolvedValue({
    item: summary({ id: 11, state: 'committed', committed_recipe_id: 77 }),
    batch_deleted: false,
  })
  renderPage()
  await screen.findByRole('region', { name: 'Incoming recipe' })

  fireEvent.click(screen.getByRole('button', { name: 'Commit as draft' }))

  await waitFor(() => expect(catalogApi.imports.commitItem).toHaveBeenCalledWith('7', 11))
  await waitFor(() => expect(screen.getByLabelText('Title')).toHaveValue('Minestrone'))
})

test('leaves the batch behind when skipping the last item empties it', async () => {
  catalogApi.imports.get.mockResolvedValue(batch([UNRESOLVED]))
  catalogApi.imports.item.mockResolvedValue(UNRESOLVED)
  catalogApi.imports.skipItem.mockResolvedValue({
    item: summary({ id: 11, state: 'skipped' }),
    batch_deleted: true,
  })
  renderPage()
  await screen.findByRole('region', { name: 'Incoming recipe' })

  fireEvent.click(screen.getByRole('button', { name: 'Skip' }))

  expect(await screen.findByText('Import overview')).toBeInTheDocument()
  // The page must stop asking about a batch the server has pruned.
  expect(catalogApi.imports.get).toHaveBeenCalledTimes(1)
})

// --- Image ------------------------------------------------------------------

test('attaches an image through the recipe upload endpoint', async () => {
  recipesApi.uploadImage.mockResolvedValue('https://img.test/pasta.png')
  catalogApi.imports.saveItem.mockResolvedValue(detail({ id: 11, problems: [] }))
  renderPage()
  await screen.findByRole('region', { name: 'Incoming recipe' })

  const file = new File(['x'], 'pasta.png', { type: 'image/png' })
  fireEvent.change(screen.getByLabelText('Recipe image'), { target: { files: [file] } })

  await waitFor(() => expect(recipesApi.uploadImage).toHaveBeenCalledWith(file))
  fireEvent.click(screen.getByRole('button', { name: 'Save draft' }))
  await waitFor(() =>
    expect(catalogApi.imports.saveItem.mock.calls.at(-1)[2].image_url).toBe('https://img.test/pasta.png'),
  )
})
