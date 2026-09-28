/**
 * @vitest-environment jsdom
 */
import { afterEach, expect, test, vi } from 'vitest'
import { catalogApi } from '../catalogApi'

// The system vocabulary writes and the import-staging calls. The URL, the verb
// and -- for the partial PUTs -- the exact body are the contract: an omitted
// key leaves the stored value alone, an explicit null clears it, and an
// unknown key is a 422 (every admin body forbids extras).

function mockFetch(body, { status = 200 } = {}) {
  globalThis.fetch = vi.fn(() =>
    Promise.resolve({
      ok: status < 400,
      status,
      json: () => Promise.resolve(body),
      text: () => Promise.resolve(JSON.stringify(body)),
    })
  )
}

const callOf = (call = 0) => globalThis.fetch.mock.calls[call]
const pathOf = (call = 0) => new URL(callOf(call)[0], 'http://x.test').pathname
const methodOf = (call = 0) => callOf(call)[1].method ?? 'GET'
const bodyOf = (call = 0) => JSON.parse(callOf(call)[1].body)

afterEach(() => {
  vi.restoreAllMocks()
})

// --- system vocabulary ------------------------------------------------------

test('createIngredient POSTs the ingredient to /admin/catalog/ingredients', async () => {
  const created = {
    id: 7,
    name: 'Chestnut',
    season_months: [10, 11],
    categories: ['produce'],
    grams_per_ml: null,
    grams_per_piece: 8,
    preferred_dimension: 'piece',
  }
  mockFetch(created, { status: 201 })

  const row = await catalogApi.admin.createIngredient({
    name: 'Chestnut',
    season_months: [10, 11],
    categories: ['produce'],
    grams_per_piece: 8,
    preferred_dimension: 'piece',
  })

  expect(row).toEqual(created)
  expect(pathOf()).toBe('/admin/catalog/ingredients')
  expect(methodOf()).toBe('POST')
  expect(bodyOf().name).toBe('Chestnut')
})

test('updateIngredient PUTs only the keys it was given, so the rest are left alone', async () => {
  mockFetch({ id: 7, name: 'Chestnut' })

  await catalogApi.admin.updateIngredient(7, { season_months: [9, 10] })

  expect(pathOf()).toBe('/admin/catalog/ingredients/7')
  expect(methodOf()).toBe('PUT')
  expect(bodyOf()).toEqual({ season_months: [9, 10] })
})

test('updateIngredient keeps an explicit null, which is how a value is cleared', async () => {
  mockFetch({ id: 7, name: 'Chestnut' })

  await catalogApi.admin.updateIngredient(7, { grams_per_piece: null })

  expect(bodyOf()).toEqual({ grams_per_piece: null })
})

test('deleteIngredient DELETEs, and the in-use 409 surfaces as its plain detail', async () => {
  mockFetch(null, { status: 204 })
  await catalogApi.admin.deleteIngredient(7)
  expect(pathOf()).toBe('/admin/catalog/ingredients/7')
  expect(methodOf()).toBe('DELETE')

  mockFetch({ detail: 'Chestnut is used by 2 recipe(s)' }, { status: 409 })
  await expect(catalogApi.admin.deleteIngredient(7)).rejects.toThrow('Chestnut is used by 2 recipe(s)')
})

test('tag writes hit /admin/catalog/tags with the verb each one needs', async () => {
  mockFetch({ id: 3, name: 'soup', penalize_repetition: true }, { status: 201 })
  await catalogApi.admin.createTag({ name: 'soup', penalize_repetition: true })
  expect(pathOf()).toBe('/admin/catalog/tags')
  expect(methodOf()).toBe('POST')
  expect(bodyOf()).toEqual({ name: 'soup', penalize_repetition: true })

  mockFetch({ id: 3, name: 'stew', penalize_repetition: true })
  await catalogApi.admin.updateTag(3, { name: 'stew' })
  expect(pathOf()).toBe('/admin/catalog/tags/3')
  expect(methodOf()).toBe('PUT')
  expect(bodyOf()).toEqual({ name: 'stew' })

  mockFetch(null, { status: 204 })
  await catalogApi.admin.deleteTag(3)
  expect(pathOf()).toBe('/admin/catalog/tags/3')
  expect(methodOf()).toBe('DELETE')
})

test('vocabulary ids are encoded, never interpolated raw', async () => {
  mockFetch(null, { status: 204 })
  await catalogApi.admin.deleteTag('a b')
  expect(callOf()[0]).toContain('/tags/a%20b')
})

// --- import staging ---------------------------------------------------------

test('imports.create POSTs the filename and the parsed entries', async () => {
  const batch = { id: 4, filename: 'pack.json', counts: { pending: 1 }, items: [] }
  mockFetch(batch, { status: 201 })

  const result = await catalogApi.imports.create('pack.json', [{ title: 'Ribollita' }])

  expect(result).toEqual(batch)
  expect(pathOf()).toBe('/admin/catalog/imports')
  expect(methodOf()).toBe('POST')
  expect(bodyOf()).toEqual({ filename: 'pack.json', entries: [{ title: 'Ribollita' }] })
})

test('imports.open GETs the open batch and passes a null one through', async () => {
  mockFetch(null)

  expect(await catalogApi.imports.open()).toBeNull()
  expect(pathOf()).toBe('/admin/catalog/imports')
  expect(methodOf()).toBe('GET')
})

test('imports.get and imports.remove address one batch', async () => {
  mockFetch({ id: 4 })
  await catalogApi.imports.get(4)
  expect(pathOf()).toBe('/admin/catalog/imports/4')

  mockFetch(null, { status: 204 })
  await catalogApi.imports.remove(4)
  expect(pathOf()).toBe('/admin/catalog/imports/4')
  expect(methodOf()).toBe('DELETE')
})

test('imports item routes read, save, skip and commit one item', async () => {
  mockFetch({ id: 2, draft: {}, duplicate: null })
  await catalogApi.imports.item(4, 2)
  expect(pathOf()).toBe('/admin/catalog/imports/4/items/2')

  mockFetch({ id: 2, draft: { title: 'Ribollita' } })
  await catalogApi.imports.saveItem(4, 2, { title: 'Ribollita' })
  expect(pathOf()).toBe('/admin/catalog/imports/4/items/2')
  expect(methodOf()).toBe('PATCH')
  expect(bodyOf()).toEqual({ draft: { title: 'Ribollita' } })

  mockFetch({ item: { id: 2, state: 'skipped' }, batch_deleted: false })
  await catalogApi.imports.skipItem(4, 2)
  expect(pathOf()).toBe('/admin/catalog/imports/4/items/2/skip')
  expect(methodOf()).toBe('POST')

  mockFetch({ item: { id: 2, state: 'committed' }, batch_deleted: true })
  const outcome = await catalogApi.imports.commitItem(4, 2)
  expect(pathOf()).toBe('/admin/catalog/imports/4/items/2/commit')
  expect(methodOf()).toBe('POST')
  expect(outcome.batch_deleted).toBe(true)
})
