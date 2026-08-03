/**
 * @vitest-environment jsdom
 */
import { render, screen, fireEvent, cleanup } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, expect, test, vi } from 'vitest'
import '@testing-library/jest-dom/vitest'
import ForgotPasswordPage from '../ForgotPasswordPage'
import { authApi } from '../../api/authApi'

vi.mock('../../api/authApi', () => ({ authApi: { forgotPassword: vi.fn() } }))

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

function renderPage() {
  return render(
    <MemoryRouter>
      <ForgotPasswordPage />
    </MemoryRouter>
  )
}

test('submits the email and shows a neutral confirmation', async () => {
  authApi.forgotPassword.mockResolvedValue({ ok: true })
  renderPage()

  fireEvent.change(screen.getByLabelText(/email/i), { target: { value: 'a@b.c' } })
  fireEvent.click(screen.getByRole('button', { name: /send reset link/i }))

  expect(await screen.findByText(/check your email/i)).toBeInTheDocument()
  expect(authApi.forgotPassword).toHaveBeenCalledWith('a@b.c')
})

test('shows the same confirmation even when the request errors', async () => {
  authApi.forgotPassword.mockRejectedValue(new Error('boom'))
  renderPage()

  fireEvent.change(screen.getByLabelText(/email/i), { target: { value: 'x@y.z' } })
  fireEvent.click(screen.getByRole('button', { name: /send reset link/i }))

  expect(await screen.findByText(/check your email/i)).toBeInTheDocument()
})
