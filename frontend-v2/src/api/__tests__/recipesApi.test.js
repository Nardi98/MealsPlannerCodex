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

// --- servings_default regression (SP-1 / SP-2) --------------------------------
// serialiseRecipe used to hardcode `servings_default: 1`, so every recipe the
// SPA saved was silently reset to "Serves 1" — including on a plain edit of a
// four-serving recipe, and that wrong number is what a share page shows.

test('normaliseRecipe keeps servings_default so an edit can round-trip it', async () => {
  mockJson({ id: 1, title: 'Ribollita', servings_default: 6 })

  const recipe = await recipesApi.fetch(1)

  expect(recipe.servings_default).toBe(6)
})

test('serialiseRecipe sends the recipe servings, not a hardcoded 1', async () => {
  mockJson({ id: 1, title: 'Ribollita', servings_default: 4 }, 201)

  await recipesApi.create({ title: 'Ribollita', servings_default: 4 })

  expect(sentBody().servings_default).toBe(4)
})

test('an edited recipe keeps its servings across a fetch/update round-trip', async () => {
  mockJson({ id: 1, title: 'Ribollita', servings_default: 6 })
  const loaded = await recipesApi.fetch(1)

  mockJson({ id: 1, title: 'Ribollita v2', servings_default: 6 })
  await recipesApi.update(1, { ...loaded, title: 'Ribollita v2' })

  expect(sentBody().servings_default).toBe(6)
})

test('servings_default falls back to 1 when the recipe carries none', async () => {
  mockJson({ id: 1, title: 'Ribollita', servings_default: 1 }, 201)

  await recipesApi.create({ title: 'Ribollita' })

  expect(sentBody().servings_default).toBe(1)
})

// --- attribution + visibility passthrough (AT-3 / AT-7) ----------------------

test('normaliseRecipe exposes visibility, copy_count and the attribution snapshot', async () => {
  mockJson({
    id: 1,
    title: 'My ribollita',
    servings_default: 2,
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

test('serialiseRecipe sends visibility but never the attribution fields (AT-4)', async () => {
  mockJson({ id: 1, title: 'My ribollita', servings_default: 2 }, 201)

  await recipesApi.create({
    title: 'My ribollita',
    servings_default: 2,
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
  mockJson({ id: 1, title: 'Ribollita', servings_default: 1 }, 201)

  await recipesApi.create({ title: 'Ribollita' })

  expect(sentBody().visibility).toBe('private')
})
