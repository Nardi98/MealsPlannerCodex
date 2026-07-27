/**
 * @vitest-environment jsdom
 */
import { request, getToken, setAuthToken, setUnauthorizedHandler } from '../client'
import { afterEach, expect, test, vi } from 'vitest'

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllEnvs()
  setAuthToken(null)
  setUnauthorizedHandler(null)
})

function jsonResponse(data, { ok = true, status = 200 } = {}) {
  return {
    ok,
    status,
    json: () => Promise.resolve(data),
    text: () => Promise.resolve(JSON.stringify(data)),
  }
}

test('attaches Authorization bearer header when a token is set', async () => {
  setAuthToken('jwt-123')
  globalThis.fetch = vi.fn(() => Promise.resolve(jsonResponse({})))

  await request('/recipes')

  const [, opts] = globalThis.fetch.mock.calls[0]
  expect(opts.headers['Authorization']).toBe('Bearer jwt-123')
})

test('holds the token in memory rather than localStorage', async () => {
  setAuthToken('jwt-abc')
  expect(getToken()).toBe('jwt-abc')
  expect(localStorage.getItem('auth_token')).toBe(null)
  setAuthToken(null)
  expect(getToken()).toBe(null)
})

test('sends credentials: include on every request', async () => {
  globalThis.fetch = vi.fn(() => Promise.resolve(jsonResponse({})))

  await request('/recipes')

  const [, opts] = globalThis.fetch.mock.calls[0]
  expect(opts.credentials).toBe('include')
})

test('does not attach Authorization header when no token is set', async () => {
  globalThis.fetch = vi.fn(() => Promise.resolve(jsonResponse({})))

  await request('/recipes')

  const [, opts] = globalThis.fetch.mock.calls[0]
  expect('Authorization' in opts.headers).toBe(false)
})

test('on 401 it refreshes once and retries the original request', async () => {
  setAuthToken('stale-jwt')
  const fetch = vi.fn()
  // 1) original request → 401
  fetch.mockResolvedValueOnce(jsonResponse({ detail: 'expired' }, { ok: false, status: 401 }))
  // 2) POST /auth/refresh → new token
  fetch.mockResolvedValueOnce(jsonResponse({ access_token: 'fresh-jwt' }))
  // 3) retried original request → success
  fetch.mockResolvedValueOnce(jsonResponse({ ok: true }))
  globalThis.fetch = fetch

  const result = await request('/recipes')

  expect(result).toEqual({ ok: true })
  expect(fetch).toHaveBeenCalledTimes(3)
  const [refreshUrl, refreshOpts] = fetch.mock.calls[1]
  expect(refreshUrl).toContain('/auth/refresh')
  expect(refreshOpts.method).toBe('POST')
  // the retry carries the refreshed token
  const [, retryOpts] = fetch.mock.calls[2]
  expect(retryOpts.headers['Authorization']).toBe('Bearer fresh-jwt')
  expect(getToken()).toBe('fresh-jwt')
})

test('when refresh fails it clears the token and invokes the unauthorized handler', async () => {
  setAuthToken('stale-jwt')
  const onUnauthorized = vi.fn()
  setUnauthorizedHandler(onUnauthorized)
  const fetch = vi.fn()
  fetch.mockResolvedValueOnce(jsonResponse({ detail: 'expired' }, { ok: false, status: 401 }))
  fetch.mockResolvedValueOnce(jsonResponse({ detail: 'no cookie' }, { ok: false, status: 401 }))
  globalThis.fetch = fetch

  await expect(request('/recipes')).rejects.toThrow()
  expect(onUnauthorized).toHaveBeenCalledTimes(1)
  expect(getToken()).toBe(null)
  // refresh is attempted exactly once — no retry storm
  expect(fetch).toHaveBeenCalledTimes(2)
})

test('does not attempt to refresh when the refresh endpoint itself 401s', async () => {
  const onUnauthorized = vi.fn()
  setUnauthorizedHandler(onUnauthorized)
  globalThis.fetch = vi.fn(() =>
    Promise.resolve(jsonResponse({ detail: 'nope' }, { ok: false, status: 401 }))
  )

  await expect(request('/auth/refresh', { method: 'POST' })).rejects.toThrow()
  expect(globalThis.fetch).toHaveBeenCalledTimes(1)
  expect(onUnauthorized).toHaveBeenCalledTimes(1)
})

test('sends application/json content-type for plain bodies', async () => {
  globalThis.fetch = vi.fn(() => Promise.resolve(jsonResponse({})))

  await request('/recipes', { method: 'POST', body: JSON.stringify({ a: 1 }) })

  const [, opts] = globalThis.fetch.mock.calls[0]
  expect(opts.headers['Content-Type']).toBe('application/json')
})

test('omits the json content-type when body is FormData', async () => {
  globalThis.fetch = vi.fn(() => Promise.resolve(jsonResponse({})))

  const fd = new FormData()
  fd.append('file', new Blob(['x']), 'x.png')
  await request('/upload', { method: 'POST', body: fd })

  const [, opts] = globalThis.fetch.mock.calls[0]
  expect(opts.headers['Content-Type']).toBeUndefined()
})
