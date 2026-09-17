/**
 * @vitest-environment jsdom
 */
import { afterEach, expect, test, vi } from 'vitest'
import { recipesApi } from '../recipesApi'

afterEach(() => {
  vi.restoreAllMocks()
})

test('uploadImage posts the file as multipart and returns the image_url', async () => {
  globalThis.fetch = vi.fn(() =>
    Promise.resolve({
      ok: true,
      status: 201,
      json: () => Promise.resolve({ image_url: 'http://api/recipes/images/recipes/a.png' }),
    })
  )

  const file = new File(['bytes'], 'a.png', { type: 'image/png' })
  const url = await recipesApi.uploadImage(file)

  expect(url).toBe('http://api/recipes/images/recipes/a.png')
  const [path, opts] = globalThis.fetch.mock.calls[0]
  expect(path).toContain('/recipes/upload-image')
  expect(opts.method).toBe('POST')
  expect(opts.body).toBeInstanceOf(FormData)
  expect(opts.body.get('file')).toBe(file)
})

function mockJson(body, status = 200) {
  globalThis.fetch = vi.fn(() =>
    Promise.resolve({ ok: true, status, json: () => Promise.resolve(body) })
  )
  return globalThis.fetch
}

function sentBody() {
  return JSON.parse(globalThis.fetch.mock.calls[0][1].body)
}

// A recipe's ingredient quantities are stored as authored, for `servings`
// people. The field round-trips in both directions.

test('serialiseRecipe sends the servings basis', async () => {
  mockJson({ id: 1, title: 'Ribollita', servings: 4 }, 201)

  await recipesApi.create({ title: 'Ribollita', servings: 4 })

  expect(sentBody().servings).toBe(4)
})

test('serialiseRecipe defaults an absent servings basis to one', async () => {
  mockJson({ id: 1, title: 'Toast' }, 201)

  await recipesApi.create({ title: 'Toast' })

  expect(sentBody().servings).toBe(1)
})

test('normaliseRecipe exposes the servings basis', async () => {
  mockJson({ id: 1, title: 'Ribollita', servings: 6 })

  const recipe = await recipesApi.fetch(1)

  expect(recipe.servings).toBe(6)
})

test('normaliseRecipe defaults servings to one when the backend omits it', async () => {
  mockJson({ id: 1, title: 'Toast' })

  expect((await recipesApi.fetch(1)).servings).toBe(1)
})

// --- attribution + visibility passthrough (AT-3 / AT-7) ----------------------

test('normaliseRecipe exposes visibility, copy_count and the attribution snapshot', async () => {
  mockJson({
    id: 1,
    title: 'My ribollita',
    visibility: 'unlisted',
    copy_count: 3,
    source_author_username: 'anna',
    source_recipe_title: 'Ribollita',
    copied_at: '2026-08-01T10:00:00',
  })

  const recipe = await recipesApi.fetch(1)

  expect(recipe.visibility).toBe('unlisted')
  expect(recipe.copy_count).toBe(3)
  expect(recipe.source_author_username).toBe('anna')
  expect(recipe.source_recipe_title).toBe('Ribollita')
  expect(recipe.copied_at).toBe('2026-08-01T10:00:00')
})

// UI-10: AttributionLine needs to know a copy came from the recipe library.
test('normaliseRecipe passes from_library through', async () => {
  mockJson({ id: 1, title: 'Ribollita', from_library: true })

  expect((await recipesApi.fetch(1)).from_library).toBe(true)
})

test('normaliseRecipe defaults from_library to false when the backend omits it', async () => {
  mockJson({ id: 1, title: 'Ribollita' })

  expect((await recipesApi.fetch(1)).from_library).toBe(false)
})

test('serialiseRecipe never sends from_library', async () => {
  mockJson({ id: 1, title: 'Ribollita' }, 201)

  await recipesApi.create({ title: 'Ribollita', from_library: true })

  expect(sentBody()).not.toHaveProperty('from_library')
})

test('serialiseRecipe sends visibility but never the attribution fields (AT-4)', async () => {
  mockJson({ id: 1, title: 'My ribollita' }, 201)

  await recipesApi.create({
    title: 'My ribollita',
    visibility: 'unlisted',
    copy_count: 3,
    source_author_username: 'attacker',
    source_recipe_title: 'forged',
    copied_at: '2026-08-01T10:00:00',
  })

  const body = sentBody()
  expect(body.visibility).toBe('unlisted')
  expect(body).not.toHaveProperty('copy_count')
  expect(body).not.toHaveProperty('source_author_username')
  expect(body).not.toHaveProperty('source_recipe_title')
  expect(body).not.toHaveProperty('copied_at')
})

test('visibility defaults to private when the caller does not set it (VIS-2)', async () => {
  mockJson({ id: 1, title: 'Ribollita' }, 201)

  await recipesApi.create({ title: 'Ribollita' })

  expect(sentBody().visibility).toBe('private')
})

// Unification is a read-time job, so the physics have to survive the trip from
// the API into the shopping list along with the amounts.
test('a recipe line keeps the ingredient conversions the API sent', async () => {
  mockJson({
      id: 1,
      title: 'Soffritto',
      servings: 2,
      ingredients: [
        {
          id: 4,
          name: 'Onion',
          quantity: 2,
          unit: 'piece',
          grams_per_ml: null,
          grams_per_piece: 150,
          preferred_dimension: 'mass',
        },
      ],
  })

  const recipe = await recipesApi.fetch(1)

  expect(recipe.ingredients[0]).toMatchObject({
    grams_per_piece: 150,
    grams_per_ml: null,
    preferred_dimension: 'mass',
  })
})

// An import learns physical facts about an ingredient; the recipe payload is
// what carries them to the server, which applies the database-wins backfill.
// If they were dropped here, imports would silently stop teaching the pantry.
test('a saved recipe carries the conversions its lines learned', async () => {
  const fetchMock = mockJson({ id: 1, title: 'Soffritto', ingredients: [] })

  await recipesApi.create({
    title: 'Soffritto',
    ingredients: [
      { name: 'Onion', amount: 2, unit: 'piece', grams_per_piece: 150 },
    ],
  })

  const sent = JSON.parse(fetchMock.mock.calls[0][1].body)
  expect(sent.ingredients[0]).toMatchObject({
    grams_per_piece: 150,
    grams_per_ml: null,
  })
})
