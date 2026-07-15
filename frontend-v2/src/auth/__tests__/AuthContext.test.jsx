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
  authApi: { login: vi.fn(), register: vi.fn(), me: vi.fn() },
}))

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
  localStorage.clear()
})

beforeEach(() => {
  client.setAuthToken(null)
})

function Probe() {
  const { user, loading } = useAuth()
  if (loading) return <div>loading</div>
  return <div>{user ? user.email : 'anonymous'}</div>
}

function Controls() {
  const { login, register, logout } = useAuth()
  return (
    <div>
      <button onClick={() => login({ email: 'a@b.c', password: 'pw' })}>login</button>
      <button onClick={() => register({ email: 'n@b.c', password: 'pw' })}>register</button>
      <button onClick={() => logout()}>logout</button>
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

test('starts anonymous when no token is stored', async () => {
  renderAuth()
  expect(await screen.findByText('anonymous')).toBeInTheDocument()
  expect(authApi.me).not.toHaveBeenCalled()
})

test('hydrates the user from a stored token on mount', async () => {
  client.setAuthToken('stored-jwt')
  authApi.me.mockResolvedValue({ id: 1, email: 'hydrated@b.c' })

  renderAuth()

  expect(await screen.findByText('hydrated@b.c')).toBeInTheDocument()
  expect(authApi.me).toHaveBeenCalledTimes(1)
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

test('logout clears the user and the token', async () => {
  client.setAuthToken('stored-jwt')
  authApi.me.mockResolvedValue({ id: 1, email: 'hydrated@b.c' })

  renderAuth()
  await screen.findByText('hydrated@b.c')

  await act(async () => {
    screen.getByText('logout').click()
  })

  expect(await screen.findByText('anonymous')).toBeInTheDocument()
  expect(client.getToken()).toBe(null)
})

test('register creates the account then logs in', async () => {
  authApi.register.mockResolvedValue({ id: 3, email: 'n@b.c' })
  authApi.login.mockResolvedValue({ access_token: 'reg-jwt' })
  authApi.me.mockResolvedValue({ id: 3, email: 'n@b.c' })

  renderAuth()
  await screen.findByText('anonymous')

  await act(async () => {
    screen.getByText('register').click()
  })

  expect(await screen.findByText('n@b.c')).toBeInTheDocument()
  expect(authApi.register).toHaveBeenCalledTimes(1)
  expect(client.getToken()).toBe('reg-jwt')
})
