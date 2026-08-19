/**
 * @vitest-environment jsdom
 */
import { render, screen, act, cleanup } from '@testing-library/react'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import '@testing-library/jest-dom/vitest'
import { AuthProvider, useAuth } from '../AuthContext'
import { authApi } from '../../api/authApi'
import * as client from '../../api/client'

vi.mock('../../api/authApi', () => ({
  authApi: {
    login: vi.fn(),
    register: vi.fn(),
    me: vi.fn(),
    google: vi.fn(),
    refresh: vi.fn(),
    logout: vi.fn(),
  },
}))

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

beforeEach(() => {
  client.setAuthToken(null)
  // Default: no refresh cookie → anonymous.
  authApi.refresh.mockRejectedValue(new Error('no cookie'))
  authApi.logout.mockResolvedValue(null)
})

function Probe() {
  const { user, loading } = useAuth()
  if (loading) return <div>loading</div>
  return <div>{user ? user.email : 'anonymous'}</div>
}

function Controls() {
  const { login, register, logout, loginWithGoogle, refreshUser } = useAuth()
  return (
    <div>
      <button onClick={() => login({ email: 'a@b.c', password: 'pw' })}>login</button>
      <button onClick={() => register({ email: 'n@b.c', password: 'pw' })}>register</button>
      <button onClick={() => logout()}>logout</button>
      <button onClick={() => loginWithGoogle('google-id-token')}>google</button>
      {/* Swallowed here only so a deliberate rejection in one test does not
          surface as an unhandled promise; the assertions cover the outcome. */}
      <button onClick={() => refreshUser().catch(() => {})}>refresh-user</button>
    </div>
  )
}

function renderAuth() {
  return render(
    <AuthProvider>
      <Probe />
      <Controls />
    </AuthProvider>
  )
}

test('starts anonymous when the refresh cookie is missing', async () => {
  renderAuth()
  expect(await screen.findByText('anonymous')).toBeInTheDocument()
  expect(authApi.me).not.toHaveBeenCalled()
})

test('restores the session from the refresh cookie on mount', async () => {
  authApi.refresh.mockResolvedValue({ access_token: 'restored-jwt' })
  authApi.me.mockResolvedValue({ id: 1, email: 'hydrated@b.c' })

  renderAuth()

  expect(await screen.findByText('hydrated@b.c')).toBeInTheDocument()
  expect(authApi.refresh).toHaveBeenCalledTimes(1)
  expect(client.getToken()).toBe('restored-jwt')
})

test('login stores the token and sets the user', async () => {
  authApi.login.mockResolvedValue({ access_token: 'new-jwt' })
  authApi.me.mockResolvedValue({ id: 2, email: 'a@b.c' })

  renderAuth()
  await screen.findByText('anonymous')

  await act(async () => {
    screen.getByText('login').click()
  })

  expect(await screen.findByText('a@b.c')).toBeInTheDocument()
  expect(client.getToken()).toBe('new-jwt')
})

test('loginWithGoogle exchanges the ID token and sets the user', async () => {
  authApi.google.mockResolvedValue({ access_token: 'google-jwt' })
  authApi.me.mockResolvedValue({ id: 4, email: 'gina@gmail.com' })

  renderAuth()
  await screen.findByText('anonymous')

  await act(async () => {
    screen.getByText('google').click()
  })

  expect(await screen.findByText('gina@gmail.com')).toBeInTheDocument()
  expect(authApi.google).toHaveBeenCalledWith({ credential: 'google-id-token' })
  expect(client.getToken()).toBe('google-jwt')
})

test('logout calls the server, clears the user and the token', async () => {
  authApi.refresh.mockResolvedValue({ access_token: 'restored-jwt' })
  authApi.me.mockResolvedValue({ id: 1, email: 'hydrated@b.c' })

  renderAuth()
  await screen.findByText('hydrated@b.c')

  await act(async () => {
    screen.getByText('logout').click()
  })

  expect(await screen.findByText('anonymous')).toBeInTheDocument()
  expect(authApi.logout).toHaveBeenCalledTimes(1)
  expect(client.getToken()).toBe(null)
})

// D-7: the handle gate keys off `username_confirmed` from /auth/me, so once the
// handle is confirmed the app needs a way to re-read the account without a full
// reload — otherwise the gate would never let go.
test('refreshUser re-reads the account and replaces the cached user', async () => {
  authApi.refresh.mockResolvedValue({ access_token: 'restored-jwt' })
  authApi.me.mockResolvedValue({ id: 1, email: 'hydrated@b.c', username_confirmed: false })

  renderAuth()
  await screen.findByText('hydrated@b.c')

  authApi.me.mockResolvedValue({ id: 1, email: 'confirmed@b.c', username_confirmed: true })
  await act(async () => {
    screen.getByText('refresh-user').click()
  })

  expect(await screen.findByText('confirmed@b.c')).toBeInTheDocument()
  expect(authApi.me).toHaveBeenCalledTimes(2)
})

// A transient /auth/me failure must not silently drop the session; the caller
// gets the rejection and the existing user stays put.
test('refreshUser leaves the session alone when the reload fails', async () => {
  authApi.refresh.mockResolvedValue({ access_token: 'restored-jwt' })
  authApi.me.mockResolvedValue({ id: 1, email: 'hydrated@b.c' })

  renderAuth()
  await screen.findByText('hydrated@b.c')

  authApi.me.mockRejectedValue(new Error('boom'))
  await act(async () => {
    screen.getByText('refresh-user').click()
  })

  expect(await screen.findByText('hydrated@b.c')).toBeInTheDocument()
  expect(client.getToken()).toBe('restored-jwt')
})

test('register creates the account but does NOT log in', async () => {
  authApi.register.mockResolvedValue({ id: 3, email: 'n@b.c' })

  renderAuth()
  await screen.findByText('anonymous')

  await act(async () => {
    screen.getByText('register').click()
  })

  expect(authApi.register).toHaveBeenCalledTimes(1)
  expect(authApi.login).not.toHaveBeenCalled()
  expect(await screen.findByText('anonymous')).toBeInTheDocument()
  expect(client.getToken()).toBe(null)
})
