/**
 * @vitest-environment jsdom
 */
/**
 * @vitest-environment jsdom
 */
import { request, setAuthToken, setUnauthorizedHandler } from '../client'
import { afterEach, expect, test, vi } from 'vitest'

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllEnvs()
  setAuthToken(null)
  setUnauthorizedHandler(null)
})

test('attaches Authorization bearer header when a token is set', async () => {
  setAuthToken('jwt-123')
  globalThis.fetch = vi.fn(() =>
    Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({}) })
  )

  await request('/recipes')

  const [, opts] = globalThis.fetch.mock.calls[0]
  expect(opts.headers['Authorization']).toBe('Bearer jwt-123')
})

test('persists the token to localStorage so it survives a reload', async () => {
  setAuthToken('jwt-abc')
  expect(localStorage.getItem('auth_token')).toBe('jwt-abc')
  setAuthToken(null)
  expect(localStorage.getItem('auth_token')).toBe(null)
})

test('does not attach Authorization header when no token is set', async () => {
  globalThis.fetch = vi.fn(() =>
    Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({}) })
  )

  await request('/recipes')

  const [, opts] = globalThis.fetch.mock.calls[0]
  expect('Authorization' in opts.headers).toBe(false)
})

test('invokes the unauthorized handler and clears the token on 401', async () => {
  setAuthToken('jwt-expired')
  const onUnauthorized = vi.fn()
  setUnauthorizedHandler(onUnauthorized)
  globalThis.fetch = vi.fn(() =>
    Promise.resolve({ ok: false, status: 401, text: () => Promise.resolve('{"detail":"nope"}') })
  )

  await expect(request('/recipes')).rejects.toThrow()
  expect(onUnauthorized).toHaveBeenCalledTimes(1)
  expect(localStorage.getItem('auth_token')).toBe(null)
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
