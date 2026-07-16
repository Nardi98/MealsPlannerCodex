/**
 * @vitest-environment jsdom
 */
import { render, screen, waitFor, cleanup } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import '@testing-library/jest-dom/vitest'
import GoogleSignInButton from '../GoogleSignInButton'
import { loadGoogleIdentityServices } from '../../auth/googleSignIn'

vi.mock('../../auth/googleSignIn', () => ({
  loadGoogleIdentityServices: vi.fn(),
}))

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
  vi.unstubAllEnvs()
})

function mockGis() {
  const id = { initialize: vi.fn(), renderButton: vi.fn() }
  loadGoogleIdentityServices.mockResolvedValue(id)
  return id
}

test('initializes Google Identity Services with the configured client id', async () => {
  vi.stubEnv('VITE_GOOGLE_CLIENT_ID', 'client-123')
  const id = mockGis()

  render(<GoogleSignInButton onCredential={vi.fn()} />)

  await waitFor(() => expect(id.initialize).toHaveBeenCalled())
  expect(id.initialize.mock.calls[0][0].client_id).toBe('client-123')
  expect(id.renderButton).toHaveBeenCalled()
})

test('passes the credential from the Google callback to onCredential', async () => {
  vi.stubEnv('VITE_GOOGLE_CLIENT_ID', 'client-123')
  const id = mockGis()
  const onCredential = vi.fn()

  render(<GoogleSignInButton onCredential={onCredential} />)
  await waitFor(() => expect(id.initialize).toHaveBeenCalled())

  const { callback } = id.initialize.mock.calls[0][0]
  callback({ credential: 'google-id-token' })

  expect(onCredential).toHaveBeenCalledWith('google-id-token')
})

test('explains that sign-in is unavailable when no client id is configured', async () => {
  vi.stubEnv('VITE_GOOGLE_CLIENT_ID', '')

  render(<GoogleSignInButton onCredential={vi.fn()} />)

  expect(await screen.findByText(/google sign-in is not configured/i)).toBeInTheDocument()
  expect(loadGoogleIdentityServices).not.toHaveBeenCalled()
})
