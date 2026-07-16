/**
 * @vitest-environment jsdom
 */
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import '@testing-library/jest-dom/vitest'
import LoginPage from '../LoginPage'

const login = vi.fn()
const register = vi.fn()
const loginWithGoogle = vi.fn()

vi.mock('../../auth/AuthContext', () => ({
  useAuth: () => ({ login, register, loginWithGoogle }),
}))

// The real button talks to Google's SDK; here we only care that the page hands
// a returned credential to the auth context.
vi.mock('../../components/GoogleSignInButton', () => ({
  default: ({ onCredential }) => (
    <button type="button" onClick={() => onCredential('google-id-token')}>
      Continue with Google
    </button>
  ),
}))

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

test('submits the login form with entered credentials', async () => {
  login.mockResolvedValue({})
  render(<LoginPage />)

  fireEvent.change(screen.getByLabelText(/email/i), { target: { value: 'a@b.c' } })
  fireEvent.change(screen.getByLabelText(/password/i), { target: { value: 'secret' } })
  fireEvent.click(screen.getByRole('button', { name: /log in/i }))

  await waitFor(() =>
    expect(login).toHaveBeenCalledWith({ email: 'a@b.c', password: 'secret' })
  )
})

test('switches to the register form and submits it', async () => {
  register.mockResolvedValue({})
  render(<LoginPage />)

  fireEvent.click(screen.getByRole('button', { name: /create an account/i }))

  fireEvent.change(screen.getByLabelText(/email/i), { target: { value: 'n@b.c' } })
  fireEvent.change(screen.getByLabelText(/password/i), { target: { value: 'pw' } })
  fireEvent.click(screen.getByRole('button', { name: /sign up/i }))

  await waitFor(() =>
    expect(register).toHaveBeenCalledWith(
      expect.objectContaining({ email: 'n@b.c', password: 'pw' })
    )
  )
})

test('shows an error message when login fails', async () => {
  login.mockRejectedValue(new Error('Invalid email or password'))
  render(<LoginPage />)

  fireEvent.change(screen.getByLabelText(/email/i), { target: { value: 'a@b.c' } })
  fireEvent.change(screen.getByLabelText(/password/i), { target: { value: 'bad' } })
  fireEvent.click(screen.getByRole('button', { name: /log in/i }))

  expect(await screen.findByText(/invalid email or password/i)).toBeInTheDocument()
})

test('renders a Google sign-in button', () => {
  render(<LoginPage />)
  expect(screen.getByRole('button', { name: /google/i })).toBeInTheDocument()
})

test('signs in with the credential returned by Google', async () => {
  loginWithGoogle.mockResolvedValue({})
  render(<LoginPage />)

  fireEvent.click(screen.getByRole('button', { name: /google/i }))

  await waitFor(() => expect(loginWithGoogle).toHaveBeenCalledWith('google-id-token'))
})

test('shows an error when Google sign-in is rejected', async () => {
  loginWithGoogle.mockRejectedValue(new Error('Invalid Google credential'))
  render(<LoginPage />)

  fireEvent.click(screen.getByRole('button', { name: /google/i }))

  expect(await screen.findByText(/invalid google credential/i)).toBeInTheDocument()
})
