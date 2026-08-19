/**
 * @vitest-environment jsdom
 */
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import '@testing-library/jest-dom/vitest'
import LoginPage from '../LoginPage'

const login = vi.fn()
const register = vi.fn()
const loginWithGoogle = vi.fn()

const checkUsername = vi.fn()

vi.mock('../../auth/AuthContext', () => ({
  useAuth: () => ({ login, register, loginWithGoogle }),
}))

// Only the network call is faked; `validatePassword` stays real so the password
// policy tests below keep exercising the shipped rules.
vi.mock('../../api/authApi', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    authApi: { ...actual.authApi, checkUsername: (...args) => checkUsername(...args) },
  }
})

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

beforeEach(() => {
  checkUsername.mockResolvedValue({ available: true, reason: null })
})

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

// UN-5/UN-7: the registration form checks the handle as the user types, through
// the shared field rather than a second implementation.
test('checks the typed handle against the server while registering', async () => {
  renderPage()

  fireEvent.click(screen.getByRole('button', { name: /create an account/i }))
  fireEvent.change(screen.getByLabelText(/username/i), { target: { value: 'ChefAnna' } })

  await waitFor(() => expect(checkUsername).toHaveBeenCalledWith('chefanna'))
  expect(await screen.findByRole('status')).toHaveTextContent(/available/i)
})

test('tells the user inline when the typed handle is taken', async () => {
  checkUsername.mockResolvedValue({ available: false, reason: 'taken' })
  renderPage()

  fireEvent.click(screen.getByRole('button', { name: /create an account/i }))
  fireEvent.change(screen.getByLabelText(/username/i), { target: { value: 'chefanna' } })

  expect(await screen.findByRole('status')).toHaveTextContent(/already taken/i)
})

test('blocks register and flags the field when no handle is given', async () => {
  renderPage()

  fillRegistration({ username: '   ' })
  fireEvent.click(screen.getByRole('button', { name: /sign up/i }))

  expect(await screen.findByRole('alert')).toHaveTextContent(/username/i)
  expect(register).not.toHaveBeenCalled()
})

// The 409 from /auth/register is about the handle. Rendering it as a general
// form failure would let a user read it as a statement about the email, which
// the backend deliberately keeps neutral.
function rejectRegistrationWith(message, status) {
  const error = new Error(message)
  if (status !== undefined) error.status = status
  register.mockRejectedValue(error)
}

test('attaches a rejected-handle error to the username field', async () => {
  rejectRegistrationWith('That username is taken', 409)
  renderPage()

  fillRegistration()
  fireEvent.click(screen.getByRole('button', { name: /sign up/i }))

  expect(await screen.findByRole('alert')).toHaveTextContent(/that username is taken/i)
  expect(screen.getByLabelText(/username/i)).toHaveAttribute('aria-invalid', 'true')
})

// The next two pin the *mechanism* the routing uses, because the two available
// mechanisms disagree on exactly these cases. Matching `/username/i` against
// the backend's prose works only for as long as the backend keeps saying
// "username" for a conflict and never says it for anything else — neither of
// which is a promise anyone made. `error.status` is the contract: 409 means
// "the handle is unavailable", in every language and after any rewording.
test('routes a 409 to the username field even when the wording changes', async () => {
  rejectRegistrationWith('Quel nome utente non è disponibile', 409)
  renderPage()

  fillRegistration()
  fireEvent.click(screen.getByRole('button', { name: /sign up/i }))

  await screen.findByRole('alert')
  expect(screen.getByLabelText(/username/i)).toHaveAttribute('aria-invalid', 'true')
})

test('does not blame the username field for a server error that merely mentions it', async () => {
  // The misfire prose-matching produces: a 500 whose message happens to
  // contain the word, marking a field invalid that the user cannot fix.
  rejectRegistrationWith('Could not save the username column right now', 500)
  renderPage()

  fillRegistration()
  fireEvent.click(screen.getByRole('button', { name: /sign up/i }))

  expect(await screen.findByRole('alert')).toHaveTextContent(/could not save/i)
  expect(screen.getByLabelText(/username/i)).not.toHaveAttribute('aria-invalid')
})

test('leaves a non-handle registration failure on the form, not on the field', async () => {
  rejectRegistrationWith('Registration is temporarily unavailable', 503)
  renderPage()

  fillRegistration()
  fireEvent.click(screen.getByRole('button', { name: /sign up/i }))

  expect(await screen.findByRole('alert')).toHaveTextContent(/temporarily unavailable/i)
  expect(screen.getByLabelText(/username/i)).not.toHaveAttribute('aria-invalid')
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
