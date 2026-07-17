/**
 * @vitest-environment jsdom
 */
import { authApi } from '../authApi'
import { afterEach, expect, test, vi } from 'vitest'

afterEach(() => {
  vi.restoreAllMocks()
})

function mockJson(data) {
  globalThis.fetch = vi.fn(() =>
    Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(data) })
  )
}

test('register posts email/password/display_name to /auth/register', async () => {
  mockJson({ id: 1, email: 'a@b.c', auth_provider: 'local' })

  const result = await authApi.register({ email: 'a@b.c', password: 'pw', display_name: 'A' })

  const [url, opts] = globalThis.fetch.mock.calls[0]
  expect(url).toContain('/auth/register')
  expect(opts.method).toBe('POST')
  expect(JSON.parse(opts.body)).toEqual({ email: 'a@b.c', password: 'pw', display_name: 'A' })
  expect(result).toEqual({ id: 1, email: 'a@b.c', auth_provider: 'local' })
})

test('login posts credentials to /auth/login and returns the token', async () => {
  mockJson({ access_token: 'jwt', token_type: 'bearer' })

  const result = await authApi.login({ email: 'a@b.c', password: 'pw' })

  const [url, opts] = globalThis.fetch.mock.calls[0]
  expect(url).toContain('/auth/login')
  expect(opts.method).toBe('POST')
  expect(JSON.parse(opts.body)).toEqual({ email: 'a@b.c', password: 'pw' })
  expect(result.access_token).toBe('jwt')
})

test('google posts the ID token to /auth/google and returns our token', async () => {
  mockJson({ access_token: 'jwt', token_type: 'bearer' })

  const result = await authApi.google({ credential: 'google-id-token' })

  const [url, opts] = globalThis.fetch.mock.calls[0]
  expect(url).toContain('/auth/google')
  expect(opts.method).toBe('POST')
  expect(JSON.parse(opts.body)).toEqual({ credential: 'google-id-token' })
  expect(result.access_token).toBe('jwt')
})

test('me fetches the current user from /auth/me', async () => {
  mockJson({ id: 1, email: 'a@b.c', auth_provider: 'local' })

  const result = await authApi.me()

  const [url] = globalThis.fetch.mock.calls[0]
  expect(url).toContain('/auth/me')
  expect(result.email).toBe('a@b.c')
})
