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
