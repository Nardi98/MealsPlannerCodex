/**
 * @vitest-environment jsdom
 */
import { render, screen, fireEvent, waitFor, within, cleanup } from '@testing-library/react'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import '@testing-library/jest-dom/vitest'
import SystemVocabularyPage from '../SystemVocabularyPage'
import { catalogApi } from '../../api/catalogApi'
import { stubViewport } from '../../test/stubViewport'

// Only the network calls are mocked; the mappers and the shared ingredient
// form stay real.
vi.mock('../../api/catalogApi', async (importOriginal) => ({
  ...(await importOriginal()),
  catalogApi: {
    admin: {
      list: vi.fn(),
      ingredients: vi.fn(),
      tags: vi.fn(),
      createIngredient: vi.fn(),
      updateIngredient: vi.fn(),
      deleteIngredient: vi.fn(),
      createTag: vi.fn(),
      updateTag: vi.fn(),
      deleteTag: vi.fn(),
    },
  },
}))

stubViewport(false)

const INGREDIENTS = [
  {
    id: 7,
    name: 'Chestnut',
    season_months: [10, 11],
    categories: ['Fruit'],
    grams_per_ml: null,
    grams_per_piece: 8,
    preferred_dimension: 'piece',
  },
  {
    id: 8,
    name: 'Kale',
    season_months: [],
    categories: ['Vegetables'],
    grams_per_ml: null,
    grams_per_piece: null,
    preferred_dimension: 'mass',
  },
]

const TAGS = [
  { id: 3, name: 'soup', penalize_repetition: true },
  { id: 4, name: 'quick', penalize_repetition: false },
]

// Two catalog recipes, so "Chestnut" is in use twice and "Kale" not at all.
const RECIPES = [
  { id: 1, title: 'Chestnut soup', tags: ['soup'], ingredients: [{ name: 'Chestnut', quantity: 100, unit: 'g' }] },
  { id: 2, title: 'Chestnut cake', tags: [], ingredients: [{ name: 'chestnut', quantity: 50, unit: 'g' }] },
]

beforeEach(() => {
  globalThis.fetch = vi.fn(() => Promise.reject(new Error('no network in tests')))
  catalogApi.admin.ingredients.mockResolvedValue(INGREDIENTS)
  catalogApi.admin.tags.mockResolvedValue(TAGS)
  catalogApi.admin.list.mockResolvedValue(RECIPES)
  catalogApi.admin.createIngredient.mockResolvedValue({ ...INGREDIENTS[0], id: 9, name: 'Leek' })
  catalogApi.admin.updateIngredient.mockResolvedValue(INGREDIENTS[0])
  catalogApi.admin.deleteIngredient.mockResolvedValue(null)
  catalogApi.admin.createTag.mockResolvedValue(TAGS[0])
  catalogApi.admin.updateTag.mockResolvedValue(TAGS[0])
  catalogApi.admin.deleteTag.mockResolvedValue(null)
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

const ingredientList = () => screen.findByRole('list', { name: 'System ingredients' })
const tagList = () => screen.findByRole('list', { name: 'System tags' })
const rowFor = async (list, text) => within(await list).getByText(text).closest('li')
const showTags = () => fireEvent.click(screen.getByRole('tab', { name: 'Tags' }))

async function renderLoaded() {
  render(<SystemVocabularyPage />)
  await screen.findByText('Chestnut')
}

test('lists the system ingredients with what is recorded about each', async () => {
  await renderLoaded()

  const row = await rowFor(ingredientList(), 'Chestnut')
  expect(row).toHaveTextContent('Fruit')
  expect(row).toHaveTextContent('2 months')
  expect(within(await ingredientList()).getByText('Kale')).toBeInTheDocument()
})

test('the search narrows the list without asking the server again', async () => {
  await renderLoaded()

  fireEvent.change(screen.getByLabelText('Search the vocabulary'), { target: { value: 'kal' } })

  await waitFor(() => expect(screen.queryByText('Chestnut')).toBeNull())
  expect(screen.getByText('Kale')).toBeInTheDocument()
  expect(catalogApi.admin.ingredients).toHaveBeenCalledTimes(1)
})

test('the tags tab lists the tags and says which penalize repetition', async () => {
  await renderLoaded()

  showTags()

  const row = await rowFor(tagList(), 'soup')
  expect(row).toHaveTextContent('Penalizes repetition')
})

test('creating an ingredient posts it and reloads the list', async () => {
  await renderLoaded()

  fireEvent.click(screen.getByRole('button', { name: 'New ingredient' }))
  fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'Leek' } })
  fireEvent.click(screen.getByRole('button', { name: 'Create ingredient' }))

  await waitFor(() =>
    expect(catalogApi.admin.createIngredient).toHaveBeenCalledWith(
      expect.objectContaining({ name: 'Leek', season_months: [], categories: [] })
    )
  )
  await waitFor(() => expect(catalogApi.admin.ingredients).toHaveBeenCalledTimes(2))
})

test('editing an ingredient sends only what changed', async () => {
  await renderLoaded()

  fireEvent.click(within(await rowFor(ingredientList(), 'Chestnut')).getByRole('button', { name: 'Edit' }))
  fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'Sweet chestnut' } })
  fireEvent.click(screen.getByRole('button', { name: 'Save ingredient' }))

  await waitFor(() =>
    expect(catalogApi.admin.updateIngredient).toHaveBeenCalledWith(7, { name: 'Sweet chestnut' })
  )
})

test('deleting an ingredient confirms with how many recipes use it', async () => {
  await renderLoaded()

  fireEvent.click(within(await rowFor(ingredientList(), 'Chestnut')).getByRole('button', { name: 'Delete' }))

  const dialog = await screen.findByRole('dialog')
  expect(dialog).toHaveTextContent('2 recipes')
  fireEvent.click(within(dialog).getByRole('button', { name: 'Delete ingredient' }))

  await waitFor(() => expect(catalogApi.admin.deleteIngredient).toHaveBeenCalledWith(7))
})

test('an in-use ingredient the server refuses reports the reason it gave', async () => {
  catalogApi.admin.deleteIngredient.mockRejectedValue(
    Object.assign(new Error('Chestnut is used by 2 recipe(s)'), {
      data: { detail: 'Chestnut is used by 2 recipe(s)' },
    })
  )
  await renderLoaded()

  fireEvent.click(within(await rowFor(ingredientList(), 'Chestnut')).getByRole('button', { name: 'Delete' }))
  fireEvent.click(within(await screen.findByRole('dialog')).getByRole('button', { name: 'Delete ingredient' }))

  expect(await screen.findByRole('alert')).toHaveTextContent('Chestnut is used by 2 recipe(s)')
})

test('a tag can be created, renamed and deleted', async () => {
  await renderLoaded()
  showTags()

  fireEvent.click(screen.getByRole('button', { name: 'New tag' }))
  fireEvent.change(screen.getByLabelText('Tag name'), { target: { value: 'stew' } })
  fireEvent.click(screen.getByRole('button', { name: 'Create tag' }))
  await waitFor(() =>
    expect(catalogApi.admin.createTag).toHaveBeenCalledWith({ name: 'stew', penalize_repetition: false })
  )

  fireEvent.click(within(await rowFor(tagList(), 'soup')).getByRole('button', { name: 'Edit' }))
  fireEvent.change(screen.getByLabelText('Tag name'), { target: { value: 'broth' } })
  fireEvent.click(screen.getByRole('button', { name: 'Save tag' }))
  await waitFor(() => expect(catalogApi.admin.updateTag).toHaveBeenCalledWith(3, { name: 'broth' }))

  fireEvent.click(within(await rowFor(tagList(), 'quick')).getByRole('button', { name: 'Delete' }))
  const dialog = await screen.findByRole('dialog')
  expect(dialog).toHaveTextContent('no recipes')
  fireEvent.click(within(dialog).getByRole('button', { name: 'Delete tag' }))
  await waitFor(() => expect(catalogApi.admin.deleteTag).toHaveBeenCalledWith(4))
})

test('a failed load offers a retry rather than an empty page', async () => {
  catalogApi.admin.ingredients.mockRejectedValue(new Error('down'))
  render(<SystemVocabularyPage />)

  fireEvent.click(await screen.findByRole('button', { name: 'Try again' }))

  await waitFor(() => expect(catalogApi.admin.ingredients).toHaveBeenCalledTimes(2))
})
