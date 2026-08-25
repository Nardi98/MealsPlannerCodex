/**
 * @vitest-environment jsdom
 */
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import { sharedWithMeApi } from '../sharedWithMeApi'

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

beforeEach(() => {
  globalThis.localStorage.clear()
  globalThis.sessionStorage.clear()
})

afterEach(() => {
  vi.restoreAllMocks()
})

test('fetchAll GETs /shared-with-me and returns the entries verbatim', async () => {
  const entry = {
    share_id: 7,
    mode: 'person',
    created_at: '2026-08-01T10:00:00',
    expires_at: null,
    recipe: {
      title: 'Ribollita',
      image_url: null,
          procedure: 'Simmer.',
      ingredients: [{ name: 'Kale', quantity: 200, unit: 'g' }],
      tags: ['soup'],
      course: 'main',
      author_display_name: 'Anna',
      author_username: 'anna',
      attribution: null,
    },
  }
  mockFetch([entry])

  const rows = await sharedWithMeApi.fetchAll()

  expect(rows).toEqual([entry])
  const [url, opts] = globalThis.fetch.mock.calls[0]
  expect(url).toContain('/shared-with-me')
  expect(opts.method ?? 'GET').toBe('GET')
})

test('fetchOne GETs the share-id keyed entry', async () => {
  mockFetch({ share_id: 7, mode: 'link', recipe: { title: 'X' } })

  const entry = await sharedWithMeApi.fetchOne(7)

  expect(entry.share_id).toBe(7)
  expect(globalThis.fetch.mock.calls[0][0]).toContain('/shared-with-me/7')
})

test('copy POSTs to the share-id copy endpoint and returns the CopyResult', async () => {
  mockFetch({ id: 42, title: 'Ribollita', already_copied: false }, { status: 201 })

  const result = await sharedWithMeApi.copy(7)

  expect(result).toEqual({ id: 42, title: 'Ribollita', already_copied: false })
  const [url, opts] = globalThis.fetch.mock.calls[0]
  expect(url).toContain('/shared-with-me/7/copy')
  expect(opts.method).toBe('POST')
})

test('dismiss POSTs to the dismiss endpoint and resolves on 204', async () => {
  globalThis.fetch = vi.fn(() =>
    Promise.resolve({ ok: true, status: 204, json: () => Promise.resolve(null) })
  )

  await expect(sharedWithMeApi.dismiss(7)).resolves.toBeNull()

  const [url, opts] = globalThis.fetch.mock.calls[0]
  expect(url).toContain('/shared-with-me/7/dismiss')
  expect(opts.method).toBe('POST')
})

test('copyByToken POSTs to /s/{token}/copy with the token URL-encoded', async () => {
  mockFetch({ id: 9, title: 'Pesto', already_copied: true }, { status: 201 })

  const result = await sharedWithMeApi.copyByToken('a b/c')

  expect(result.already_copied).toBe(true)
  const [url, opts] = globalThis.fetch.mock.calls[0]
  expect(url).toContain('/s/a%20b%2Fc/copy')
  expect(opts.method).toBe('POST')
})

test('copyByToken never persists the token to web storage', async () => {
  mockFetch({ id: 9, title: 'Pesto', already_copied: false }, { status: 201 })

  await sharedWithMeApi.copyByToken('super-secret-token')

  const dumped =
    JSON.stringify(globalThis.localStorage) + JSON.stringify(globalThis.sessionStorage)
  expect(dumped).not.toContain('super-secret-token')
  expect(globalThis.localStorage.length).toBe(0)
  expect(globalThis.sessionStorage.length).toBe(0)
})

test('a 404 surfaces the backend detail so callers can render a neutral message', async () => {
  globalThis.fetch = vi.fn(() =>
    Promise.resolve({
      ok: false,
      status: 404,
      text: () => Promise.resolve(JSON.stringify({ detail: 'Not found' })),
    })
  )

  await expect(sharedWithMeApi.fetchOne(1)).rejects.toThrow('Not found')
})
