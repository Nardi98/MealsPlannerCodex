/**
 * @vitest-environment jsdom
 */
import { afterEach, expect, test, vi } from 'vitest'
import { apiErrorText, catalogApi, recipeWriteProblem, toRecipeForm, toRecipeWrite } from '../catalogApi'

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

// The query string of the n-th fetch call, parsed so key order is irrelevant.
function paramsOf(call = 0) {
  const url = globalThis.fetch.mock.calls[call][0]
  return new URL(url, 'http://x.test').searchParams
}

afterEach(() => {
  vi.restoreAllMocks()
})

test('list GETs /catalog/recipes and returns the rows verbatim', async () => {
  const row = {
    id: 3,
    title: 'Ribollita',
    course: 'main',
    servings: 2,
    bulk_prep: true,
    image_url: null,
    tags: ['soup'],
    ingredients: [{ name: 'Kale', quantity: 200, unit: 'g' }],
    adoption_count: 4,
    in_my_book: false,
  }
  mockFetch([row])

  const rows = await catalogApi.list()

  expect(rows).toEqual([row])
  const [url, opts] = globalThis.fetch.mock.calls[0]
  expect(new URL(url, 'http://x.test').pathname).toBe('/catalog/recipes')
  expect(opts.method ?? 'GET').toBe('GET')
})

test('list repeats the course and tags keys once per value', async () => {
  mockFetch([])

  await catalogApi.list({ courses: ['main', 'side'], tags: ['vegan', 'quick'] })

  const params = paramsOf()
  expect(params.getAll('course')).toEqual(['main', 'side'])
  expect(params.getAll('tags')).toEqual(['vegan', 'quick'])
})

test('list encodes q and passes sort', async () => {
  mockFetch([])

  await catalogApi.list({ q: '50% a&b', sort: 'title' })

  const url = globalThis.fetch.mock.calls[0][0]
  expect(url).not.toContain('50% a&b')
  const params = paramsOf()
  expect(params.get('q')).toBe('50% a&b')
  expect(params.get('sort')).toBe('title')
})

test('list omits empty filters rather than sending blank keys', async () => {
  mockFetch([])

  await catalogApi.list({ courses: [], tags: [], q: '   ', sort: undefined })

  const url = globalThis.fetch.mock.calls[0][0]
  expect(url).not.toContain('?')
})

test('get GETs one catalog recipe by id', async () => {
  mockFetch({ id: 7, title: 'Pesto', procedure: 'Blend.' })

  const row = await catalogApi.get(7)

  expect(row.procedure).toBe('Blend.')
  expect(globalThis.fetch.mock.calls[0][0]).toContain('/catalog/recipes/7')
})

test('adopt POSTs {recipe_ids} and returns the result', async () => {
  mockFetch({ created_ids: [11, 12], skipped_ids: [3] })

  const result = await catalogApi.adopt([1, 2, 3])

  expect(result).toEqual({ created_ids: [11, 12], skipped_ids: [3] })
  const [url, opts] = globalThis.fetch.mock.calls[0]
  expect(url).toContain('/catalog/adopt')
  expect(opts.method).toBe('POST')
  expect(JSON.parse(opts.body)).toEqual({ recipe_ids: [1, 2, 3] })
})

test('an adopt failure surfaces the backend detail', async () => {
  mockFetch({ detail: 'At most 100 recipes per request' }, { status: 400 })

  await expect(catalogApi.adopt([])).rejects.toThrow('At most 100 recipes per request')
})

// --- Admin (spec §10.2, plan D3) ---------------------------------------------

// What NewRecipeModal's onSave hands over: the user-book form shape, with the
// pantry ids, `hot`, `amount` and the fields only a user's own recipe carries.
const FORM = {
  title: 'Ribollita',
  course: 'main',
  servings: 4,
  tags: ['soup', 'vegan'],
  ingredients: [
    { id: 17, name: 'Cavolo nero', amount: 800, unit: 'g', grams_per_ml: null, grams_per_piece: null },
    { id: 18, name: 'Olive oil', amount: 30, unit: 'ml', grams_per_ml: 0.92, grams_per_piece: null },
  ],
  procedure: 'Simmer for two hours.',
  image_url: 'http://api/recipes/images/recipes/a.png',
  hot: true,
  favorite_side_ids: [3],
}

const RECIPE_WRITE = {
  title: 'Ribollita',
  course: 'main',
  servings: 4,
  bulk_prep: true,
  procedure: 'Simmer for two hours.',
  image_url: 'http://api/recipes/images/recipes/a.png',
  tags: ['soup', 'vegan'],
  ingredients: [
    { name: 'Cavolo nero', quantity: 800, unit: 'g' },
    { name: 'Olive oil', quantity: 30, unit: 'ml' },
  ],
}

const sentBody = (call = 0) => JSON.parse(globalThis.fetch.mock.calls[call][1].body)

test('toRecipeWrite maps the form to RecipeWrite, by name, with nothing else', () => {
  expect(toRecipeWrite(FORM)).toEqual(RECIPE_WRITE)
})

test('toRecipeWrite never sends ids, user_id or visibility', () => {
  const payload = toRecipeWrite({ ...FORM, id: 9, user_id: 4, visibility: 'private' })
  const json = JSON.stringify(payload)
  expect(json).not.toMatch(/"id"|user_id|visibility|favorite_side_ids|grams_per/)
})

test('toRecipeWrite drops blank ingredient lines and sends a missing image as null', () => {
  const payload = toRecipeWrite({
    ...FORM,
    image_url: '',
    hot: undefined,
    ingredients: [{ id: undefined, name: '  ', amount: '', unit: '' }, FORM.ingredients[0]],
  })
  expect(payload.image_url).toBeNull()
  expect(payload.bulk_prep).toBe(false)
  expect(payload.ingredients).toEqual([{ name: 'Cavolo nero', quantity: 800, unit: 'g' }])
})

test('toRecipeForm turns a catalog row into the form NewRecipeModal pre-fills from', () => {
  const form = toRecipeForm({ id: 5, adoption_count: 3, status: 'published', ...RECIPE_WRITE })
  expect(form).toEqual({
    title: 'Ribollita',
    course: 'main',
    servings: 4,
    hot: true,
    procedure: 'Simmer for two hours.',
    image_url: 'http://api/recipes/images/recipes/a.png',
    tags: ['soup', 'vegan'],
    ingredients: [
      { id: undefined, name: 'Cavolo nero', amount: 800, unit: 'g' },
      { id: undefined, name: 'Olive oil', amount: 30, unit: 'ml' },
    ],
  })
  // The round trip is lossless.
  expect(toRecipeWrite(form)).toEqual(RECIPE_WRITE)
})

test('admin.list GETs /admin/catalog/recipes', async () => {
  mockFetch([{ id: 1, status: 'retired' }])

  expect(await catalogApi.admin.list()).toEqual([{ id: 1, status: 'retired' }])
  const [url, opts] = globalThis.fetch.mock.calls[0]
  expect(new URL(url, 'http://x.test').pathname).toBe('/admin/catalog/recipes')
  expect(opts.method ?? 'GET').toBe('GET')
})

test('admin.list passes q, status and sort as query parameters', async () => {
  mockFetch([])

  await catalogApi.admin.list({ q: '50% a&b', status: 'retired', sort: 'popular' })

  const url = globalThis.fetch.mock.calls[0][0]
  expect(url).not.toContain('50% a&b')
  const params = paramsOf()
  expect(params.get('q')).toBe('50% a&b')
  expect(params.get('status')).toBe('retired')
  expect(params.get('sort')).toBe('popular')
})

test('admin.list omits empty filters rather than sending blank keys', async () => {
  mockFetch([])

  await catalogApi.admin.list({ q: '   ', status: '', sort: undefined })

  expect(globalThis.fetch.mock.calls[0][0]).not.toContain('?')
})

test('admin.create POSTs the serialised recipe and publishes it', async () => {
  mockFetch({ id: 30, status: 'published' }, { status: 201 })

  const row = await catalogApi.admin.create(FORM)

  expect(row).toEqual({ id: 30, status: 'published' })
  const [url, opts] = globalThis.fetch.mock.calls[0]
  expect(new URL(url, 'http://x.test').pathname).toBe('/admin/catalog/recipes')
  expect(opts.method).toBe('POST')
  expect(sentBody()).toEqual({ ...RECIPE_WRITE, publish: true })
})

test('admin.update PUTs the serialised recipe to its id', async () => {
  mockFetch({ id: 30 })

  await catalogApi.admin.update(30, FORM)

  const [url, opts] = globalThis.fetch.mock.calls[0]
  expect(new URL(url, 'http://x.test').pathname).toBe('/admin/catalog/recipes/30')
  expect(opts.method).toBe('PUT')
  expect(sentBody()).toEqual(RECIPE_WRITE)
})

test.each([
  ['publish', '/admin/catalog/recipes/30/publish'],
  ['retire', '/admin/catalog/recipes/30/retire'],
])('admin.%s POSTs to its endpoint', async (method, path) => {
  mockFetch({ id: 30 })

  await catalogApi.admin[method](30)

  const [url, opts] = globalThis.fetch.mock.calls[0]
  expect(new URL(url, 'http://x.test').pathname).toBe(path)
  expect(opts.method).toBe('POST')
})

test.each([
  ['exportCatalog', '/admin/catalog/export'],
  ['ingredients', '/admin/catalog/ingredients'],
  ['tags', '/admin/catalog/tags'],
])('admin.%s GETs %s', async (method, path) => {
  mockFetch([])

  await catalogApi.admin[method]()

  const [url, opts] = globalThis.fetch.mock.calls[0]
  expect(new URL(url, 'http://x.test').pathname).toBe(path)
  expect(opts.method ?? 'GET').toBe('GET')
})

// --- Client-side checks mirroring RecipeWrite validation ---------------------

const withLines = (ingredients) => ({ ...FORM, ingredients })

test('recipeWriteProblem finds nothing wrong with a complete recipe', () => {
  expect(recipeWriteProblem(FORM)).toBeNull()
})

test.each([
  ['a blank amount', { amount: '' }],
  ['a zero amount', { amount: 0 }],
  ['a negative amount', { amount: -2 }],
  ['a missing unit', { unit: '' }],
])('recipeWriteProblem names the ingredient with %s', (_label, change) => {
  const form = withLines([FORM.ingredients[0], { ...FORM.ingredients[1], ...change }])
  expect(recipeWriteProblem(form)).toBe('"Olive oil" needs an amount and a unit.')
})

test('recipeWriteProblem ignores blank lines, which are never sent', () => {
  expect(recipeWriteProblem(withLines([FORM.ingredients[0], { name: ' ', amount: '', unit: '' }]))).toBeNull()
})

test('recipeWriteProblem catches a duplicate ingredient with the server message', () => {
  const form = withLines([FORM.ingredients[0], { ...FORM.ingredients[0], name: ' cavolo nero ', amount: 5 }])
  expect(recipeWriteProblem(form)).toBe('Duplicate ingredient: cavolo nero')
})

function apiError(message, data) {
  return Object.assign(new Error(message), { data })
}

test('apiErrorText keeps a string detail as the message', () => {
  const err = apiError('Unknown ingredient: Kale', { detail: 'Unknown ingredient: Kale' })
  expect(apiErrorText(err)).toBe('Unknown ingredient: Kale')
  expect(apiErrorText(new Error('Network down'))).toBe('Network down')
})

test('apiErrorText turns a 422 detail array into readable text, never JSON', () => {
  const detail = [
    { loc: ['body', 'ingredients', 0, 'quantity'], msg: 'Input should be greater than 0', type: 'greater_than' },
    { loc: ['body', 'servings'], msg: 'Input should be greater than or equal to 1', type: 'greater_than_equal' },
    { loc: ['body'], msg: 'Extra inputs are not permitted', type: 'extra_forbidden' },
  ]
  const text = apiErrorText(apiError(JSON.stringify({ detail }), { detail }))
  expect(text).toBe(
    'ingredient 1 quantity: Input should be greater than 0; ' +
      'servings: Input should be greater than or equal to 1; ' +
      'Extra inputs are not permitted',
  )
})

test('an admin failure surfaces the backend detail', async () => {
  mockFetch({ detail: 'Unknown ingredient: Kale' }, { status: 400 })

  await expect(catalogApi.admin.create(FORM)).rejects.toThrow('Unknown ingredient: Kale')
})
