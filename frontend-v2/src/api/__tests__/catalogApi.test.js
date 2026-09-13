/**
 * @vitest-environment jsdom
 */
import { afterEach, expect, test, vi } from 'vitest'
import { catalogApi } from '../catalogApi'

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
