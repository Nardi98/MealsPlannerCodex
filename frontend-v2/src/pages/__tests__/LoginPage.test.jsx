/**
 * @vitest-environment jsdom
 */
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
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

function renderPage() {
  return render(
    <MemoryRouter>
      <LoginPage />
    </MemoryRouter>
  )
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

test('submits the login form with entered credentials', async () => {
  login.mockResolvedValue({})
  renderPage()

  fireEvent.change(screen.getByLabelText(/email/i), { target: { value: 'a@b.c' } })
  fireEvent.change(screen.getByLabelText(/password/i), { target: { value: 'secret' } })
  fireEvent.click(screen.getByRole('button', { name: /log in/i }))

  await waitFor(() =>
    expect(login).toHaveBeenCalledWith({ email: 'a@b.c', password: 'secret' })
  )
})

// Fills every field the registration form requires. UN-5 adds the username, so
// each register-path test goes through here rather than repeating the sequence.
function fillRegistration({ username = 'newcook' } = {}) {
  fireEvent.click(screen.getByRole('button', { name: /create an account/i }))
  fireEvent.change(screen.getByLabelText(/email/i), { target: { value: 'n@b.c' } })
  fireEvent.change(screen.getByLabelText(/username/i), { target: { value: username } })
  fireEvent.change(screen.getByLabelText(/^password/i), { target: { value: 'Abcdef12' } })
  fireEvent.change(screen.getByLabelText(/confirm password/i), {
    target: { value: 'Abcdef12' },
  })
}

test('switches to register and submits a policy-compliant password', async () => {
  register.mockResolvedValue({ id: 3, email: 'n@b.c' })
  renderPage()

  fillRegistration()
  fireEvent.click(screen.getByRole('button', { name: /sign up/i }))

  await waitFor(() =>
    expect(register).toHaveBeenCalledWith(
      expect.objectContaining({ email: 'n@b.c', password: 'Abcdef12' })
    )
  )
})

// UN-5: the handle is chosen at registration, on the existing form.
test('sends the chosen username in the register payload', async () => {
  register.mockResolvedValue({ id: 3, email: 'n@b.c' })
  renderPage()

  fillRegistration({ username: 'ChefAnna' })
  fireEvent.click(screen.getByRole('button', { name: /sign up/i }))

  await waitFor(() => expect(register).toHaveBeenCalledTimes(1))
  // UN-3 says input is lowercased on entry rather than rejected for case.
  expect(register.mock.calls[0][0].username).toBe('chefanna')
})

test('the login form does not ask for a username', () => {
  renderPage()
  expect(screen.queryByLabelText(/username/i)).not.toBeInTheDocument()
})

test('blocks register and shows an error for a weak password', async () => {
  renderPage()

  fillRegistration()
  fireEvent.change(screen.getByLabelText(/^password/i), { target: { value: 'weak' } })
  fireEvent.change(screen.getByLabelText(/confirm password/i), { target: { value: 'weak' } })
  fireEvent.click(screen.getByRole('button', { name: /sign up/i }))

  expect(await screen.findByRole('alert')).toHaveTextContent(/at least 8/i)
  expect(register).not.toHaveBeenCalled()
})

test('blocks register when the confirm password does not match', async () => {
  renderPage()

  fillRegistration()
  fireEvent.change(screen.getByLabelText(/confirm password/i), { target: { value: 'Abcdef99' } })
  fireEvent.click(screen.getByRole('button', { name: /sign up/i }))

  expect(await screen.findByRole('alert')).toHaveTextContent(/do not match/i)
  expect(register).not.toHaveBeenCalled()
})

test('does not send the confirm value in the register payload', async () => {
  register.mockResolvedValue({ id: 3, email: 'n@b.c' })
  renderPage()

  fillRegistration()
  fireEvent.click(screen.getByRole('button', { name: /sign up/i }))

  await waitFor(() => expect(register).toHaveBeenCalledTimes(1))
  const payload = register.mock.calls[0][0]
  expect(payload).toEqual({
    email: 'n@b.c',
    password: 'Abcdef12',
    display_name: null,
    username: 'newcook',
  })
  expect(Object.keys(payload)).not.toContain('confirmPassword')
})

test('shows a check-your-email screen after registering', async () => {
  register.mockResolvedValue({ id: 3, email: 'n@b.c' })
  renderPage()

  fillRegistration()
  fireEvent.click(screen.getByRole('button', { name: /sign up/i }))

  expect(await screen.findByText(/check your email/i)).toBeInTheDocument()
  expect(screen.getByText(/n@b\.c/)).toBeInTheDocument()
})

test('shows an error message when login fails', async () => {
  login.mockRejectedValue(new Error('Invalid email or password'))
  renderPage()

  fireEvent.change(screen.getByLabelText(/email/i), { target: { value: 'a@b.c' } })
  fireEvent.change(screen.getByLabelText(/password/i), { target: { value: 'bad' } })
  fireEvent.click(screen.getByRole('button', { name: /log in/i }))

  expect(await screen.findByText(/invalid email or password/i)).toBeInTheDocument()
})

test('links to the forgot-password flow', () => {
  renderPage()
  expect(screen.getByRole('link', { name: /forgot your password/i })).toHaveAttribute(
    'href',
    '/forgot-password'
  )
})

test('renders a Google sign-in button', () => {
  renderPage()
  expect(screen.getByRole('button', { name: /google/i })).toBeInTheDocument()
})

test('signs in with the credential returned by Google', async () => {
  loginWithGoogle.mockResolvedValue({})
  renderPage()

  fireEvent.click(screen.getByRole('button', { name: /google/i }))

  await waitFor(() => expect(loginWithGoogle).toHaveBeenCalledWith('google-id-token'))
})

test('shows an error when Google sign-in is rejected', async () => {
  loginWithGoogle.mockRejectedValue(new Error('Invalid Google credential'))
  renderPage()

  fireEvent.click(screen.getByRole('button', { name: /google/i }))

  expect(await screen.findByText(/invalid google credential/i)).toBeInTheDocument()
})
