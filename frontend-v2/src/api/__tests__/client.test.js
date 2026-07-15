/**
 * @vitest-environment jsdom
 */
import { request } from '../client'
import { afterEach, expect, test, vi } from 'vitest'

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllEnvs()
})

test('attaches X-API-Key header when VITE_API_KEY is set', async () => {
  vi.stubEnv('VITE_API_KEY', 'secret')
  globalThis.fetch = vi.fn(() =>
    Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({}) })
  )

  await request('/recipes')

  const [, opts] = globalThis.fetch.mock.calls[0]
  expect(opts.headers['X-API-Key']).toBe('secret')
})

test('does not attach X-API-Key header when VITE_API_KEY is unset', async () => {
  vi.stubEnv('VITE_API_KEY', '')
  globalThis.fetch = vi.fn(() =>
    Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({}) })
  )

  await request('/recipes')

  const [, opts] = globalThis.fetch.mock.calls[0]
  expect('X-API-Key' in opts.headers).toBe(false)
})

test('sends application/json content-type for plain bodies', async () => {
  globalThis.fetch = vi.fn(() =>
    Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({}) })
  )

  await request('/recipes', { method: 'POST', body: JSON.stringify({ a: 1 }) })

  const [, opts] = globalThis.fetch.mock.calls[0]
  expect(opts.headers['Content-Type']).toBe('application/json')
})

test('omits the json content-type when body is FormData', async () => {
  globalThis.fetch = vi.fn(() =>
    Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({}) })
  )

  const fd = new FormData()
  fd.append('file', new Blob(['x']), 'x.png')
  await request('/upload', { method: 'POST', body: fd })

  const [, opts] = globalThis.fetch.mock.calls[0]
  expect(opts.headers['Content-Type']).toBeUndefined()
})
