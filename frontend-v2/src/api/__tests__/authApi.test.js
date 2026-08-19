/**
 * @vitest-environment jsdom
 */
import { authApi, validatePassword } from '../authApi'
import { afterEach, expect, test, vi } from 'vitest'

afterEach(() => {
  vi.restoreAllMocks()
})

function mockJson(data) {
  globalThis.fetch = vi.fn(() =>
    Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(data) })
  )
}

test('register posts email/password/display_name/username to /auth/register', async () => {
  mockJson({ id: 1, email: 'a@b.c', auth_provider: 'local', username: 'chef' })

  const result = await authApi.register({
    email: 'a@b.c',
    password: 'pw',
    display_name: 'A',
    username: 'chef',
  })

  const [url, opts] = globalThis.fetch.mock.calls[0]
  expect(url).toContain('/auth/register')
  expect(opts.method).toBe('POST')
  expect(JSON.parse(opts.body)).toEqual({
    email: 'a@b.c',
    password: 'pw',
    display_name: 'A',
    username: 'chef',
  })
  expect(result.username).toBe('chef')
})

// UN-1 makes the handle non-null server-side, but a caller that omits it (the
// server then derives one) must not send an explicit null and trip validation.
test('register omits username when the caller gives none', async () => {
  mockJson({ id: 1, email: 'a@b.c', auth_provider: 'local', username: 'a' })

  await authApi.register({ email: 'a@b.c', password: 'pw', display_name: null })

  const [, opts] = globalThis.fetch.mock.calls[0]
  expect(Object.keys(JSON.parse(opts.body))).not.toContain('username')
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

test('refresh posts to /auth/refresh', async () => {
  mockJson({ access_token: 'fresh', token_type: 'bearer' })

  const result = await authApi.refresh()

  const [url, opts] = globalThis.fetch.mock.calls[0]
  expect(url).toContain('/auth/refresh')
  expect(opts.method).toBe('POST')
  expect(result.access_token).toBe('fresh')
})

test('logout posts to /auth/logout', async () => {
  globalThis.fetch = vi.fn(() =>
    Promise.resolve({ ok: true, status: 204, text: () => Promise.resolve('') })
  )

  await authApi.logout()

  const [url, opts] = globalThis.fetch.mock.calls[0]
  expect(url).toContain('/auth/logout')
  expect(opts.method).toBe('POST')
})

test('verifyEmail posts the token to /auth/verify-email', async () => {
  mockJson({ ok: true })

  await authApi.verifyEmail('verify-token')

  const [url, opts] = globalThis.fetch.mock.calls[0]
  expect(url).toContain('/auth/verify-email')
  expect(JSON.parse(opts.body)).toEqual({ token: 'verify-token' })
})

test('forgotPassword posts the email to /auth/forgot-password', async () => {
  mockJson({ ok: true })

  await authApi.forgotPassword('a@b.c')

  const [url, opts] = globalThis.fetch.mock.calls[0]
  expect(url).toContain('/auth/forgot-password')
  expect(JSON.parse(opts.body)).toEqual({ email: 'a@b.c' })
})

test('resetPassword posts token and new_password to /auth/reset-password', async () => {
  mockJson({ ok: true })

  await authApi.resetPassword('reset-token', 'NewPass1')

  const [url, opts] = globalThis.fetch.mock.calls[0]
  expect(url).toContain('/auth/reset-password')
  expect(JSON.parse(opts.body)).toEqual({ token: 'reset-token', new_password: 'NewPass1' })
})

test('validatePassword accepts a policy-compliant password', () => {
  expect(validatePassword('Abcdef12')).toBe(null)
})

test('validatePassword rejects short, weak, or oversized passwords', () => {
  expect(validatePassword('Ab1')).toMatch(/at least 8/i)
  expect(validatePassword('abcdefg1')).toMatch(/uppercase/i)
  expect(validatePassword('ABCDEFG1')).toMatch(/lowercase/i)
  expect(validatePassword('Abcdefgh')).toMatch(/digit/i)
  expect(validatePassword('A1' + 'a'.repeat(71))).toMatch(/72 bytes/i)
})
