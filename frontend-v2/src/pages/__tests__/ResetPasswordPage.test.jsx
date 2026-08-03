/**
 * @vitest-environment jsdom
 */
import { render, screen, fireEvent, cleanup } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, expect, test, vi } from 'vitest'
import '@testing-library/jest-dom/vitest'
import ResetPasswordPage from '../ResetPasswordPage'
import { authApi } from '../../api/authApi'

vi.mock('../../api/authApi', async () => {
  const actual = await vi.importActual('../../api/authApi')
  return { validatePassword: actual.validatePassword, authApi: { resetPassword: vi.fn() } }
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

function renderAt(path) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <ResetPasswordPage />
    </MemoryRouter>
  )
}

test('resets the password using the token from the query string', async () => {
  authApi.resetPassword.mockResolvedValue({ ok: true })
  renderAt('/reset-password?token=tok123')

  fireEvent.change(screen.getByLabelText(/new password/i), { target: { value: 'Abcdef12' } })
  fireEvent.change(screen.getByLabelText(/confirm password/i), { target: { value: 'Abcdef12' } })
  fireEvent.click(screen.getByRole('button', { name: /reset password/i }))

  expect(await screen.findByText(/password updated/i)).toBeInTheDocument()
  expect(authApi.resetPassword).toHaveBeenCalledWith('tok123', 'Abcdef12')
})

test('rejects a weak password before calling the API', async () => {
  renderAt('/reset-password?token=tok123')

  fireEvent.change(screen.getByLabelText(/new password/i), { target: { value: 'weak' } })
  fireEvent.change(screen.getByLabelText(/confirm password/i), { target: { value: 'weak' } })
  fireEvent.click(screen.getByRole('button', { name: /reset password/i }))

  expect(await screen.findByRole('alert')).toHaveTextContent(/at least 8/i)
  expect(authApi.resetPassword).not.toHaveBeenCalled()
})

test('rejects mismatched confirmation', async () => {
  renderAt('/reset-password?token=tok123')

  fireEvent.change(screen.getByLabelText(/new password/i), { target: { value: 'Abcdef12' } })
  fireEvent.change(screen.getByLabelText(/confirm password/i), { target: { value: 'Abcdef99' } })
  fireEvent.click(screen.getByRole('button', { name: /reset password/i }))

  expect(await screen.findByRole('alert')).toHaveTextContent(/do not match/i)
  expect(authApi.resetPassword).not.toHaveBeenCalled()
})

test('errors when the token is missing', async () => {
  renderAt('/reset-password')

  fireEvent.change(screen.getByLabelText(/new password/i), { target: { value: 'Abcdef12' } })
  fireEvent.change(screen.getByLabelText(/confirm password/i), { target: { value: 'Abcdef12' } })
  fireEvent.click(screen.getByRole('button', { name: /reset password/i }))

  expect(await screen.findByRole('alert')).toHaveTextContent(/missing its token/i)
  expect(authApi.resetPassword).not.toHaveBeenCalled()
})
