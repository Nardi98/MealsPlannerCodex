/**
 * @vitest-environment jsdom
 */
import { render, screen, cleanup } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, expect, test, vi } from 'vitest'
import '@testing-library/jest-dom/vitest'
import VerifyEmailPage from '../VerifyEmailPage'
import { authApi } from '../../api/authApi'

vi.mock('../../api/authApi', () => ({ authApi: { verifyEmail: vi.fn() } }))

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

function renderAt(path) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <VerifyEmailPage />
    </MemoryRouter>
  )
}

test('verifies the token from the query string and confirms success', async () => {
  authApi.verifyEmail.mockResolvedValue({ ok: true })
  renderAt('/verify-email?token=abc123')

  expect(await screen.findByText(/your email is verified/i)).toBeInTheDocument()
  expect(authApi.verifyEmail).toHaveBeenCalledWith('abc123')
})

test('shows an error when verification fails', async () => {
  authApi.verifyEmail.mockRejectedValue(new Error('Token expired'))
  renderAt('/verify-email?token=stale')

  expect(await screen.findByRole('alert')).toHaveTextContent(/token expired/i)
})

test('shows an error when the token is missing', async () => {
  renderAt('/verify-email')

  expect(await screen.findByRole('alert')).toHaveTextContent(/missing its token/i)
  expect(authApi.verifyEmail).not.toHaveBeenCalled()
})
