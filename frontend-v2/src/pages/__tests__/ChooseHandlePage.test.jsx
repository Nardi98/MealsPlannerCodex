/**
 * @vitest-environment jsdom
 */
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'
import '@testing-library/jest-dom/vitest'
import ChooseHandlePage from '../ChooseHandlePage'

const refreshUser = vi.fn()
const checkUsername = vi.fn()
const confirmUsername = vi.fn()

// D-7: a Google sign-up is handed a provisional handle derived from the email
// local part. This is exactly the pair the page must never put on screen.
const PROVISIONAL = 'anna_rossi'
const EMAIL = 'anna.rossi@example.com'

let user

vi.mock('../../auth/AuthContext', () => ({
  useAuth: () => ({ user, refreshUser }),
}))

// `authApi.confirmUsername` does not exist yet — UN-8/UN-9 are deferred to Part
// 2. The mock supplies it so the page's intended flow can be described without
// asserting a round-trip that no backend route could serve.
vi.mock('../../api/authApi', () => ({
  authApi: {
    checkUsername: (...args) => checkUsername(...args),
    confirmUsername: (...args) => confirmUsername(...args),
  },
}))

beforeEach(() => {
  user = {
    id: 7,
    email: EMAIL,
    username: PROVISIONAL,
    username_confirmed: false,
    auth_provider: 'google',
  }
  checkUsername.mockResolvedValue({ available: true, reason: null })
  confirmUsername.mockResolvedValue({ username: 'chefanna', username_confirmed: true })
  refreshUser.mockResolvedValue(user)
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

function field() {
  return screen.getByLabelText(/username/i)
}

function submitButton() {
  return screen.getByRole('button', { name: /continue|save|confirm/i })
}

describe('UN-11 — the provisional handle is never disclosed', () => {
  test('renders neither the provisional handle nor the email anywhere', () => {
    render(<ChooseHandlePage />)

    const rendered = document.body.innerHTML
    expect(rendered).not.toContain(PROVISIONAL)
    expect(rendered).not.toContain(EMAIL)
    // The local part on its own is the disclosure UN-11 forbids, in either the
    // raw or the derived spelling.
    expect(rendered).not.toContain('anna.rossi')
    expect(rendered).not.toContain('anna_rossi')
  })

  test('starts with an empty field — not pre-filled, not placeheld', () => {
    render(<ChooseHandlePage />)

    const input = field()
    expect(input).toHaveValue('')
    expect(input.getAttribute('placeholder') || '').not.toContain('anna')
    expect(input.defaultValue).toBe('')
  })

  test('offers no suggestion built from the account', () => {
    render(<ChooseHandlePage />)

    expect(screen.queryByText(/suggest/i)).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: new RegExp(PROVISIONAL, 'i') })).not.toBeInTheDocument()
  })
})

describe('UN-6 — the step is mandatory', () => {
  test('offers no skip, dismiss, cancel or later affordance', () => {
    render(<ChooseHandlePage />)

    for (const escape of [/skip/i, /later/i, /cancel/i, /dismiss/i, /not now/i, /close/i]) {
      expect(screen.queryByRole('button', { name: escape })).not.toBeInTheDocument()
      expect(screen.queryByRole('link', { name: escape })).not.toBeInTheDocument()
    }
  })

  test('renders no navigation away from the step', () => {
    render(<ChooseHandlePage />)

    expect(screen.queryAllByRole('link')).toHaveLength(0)
  })

  test('exposes exactly one action: continue', () => {
    render(<ChooseHandlePage />)

    expect(screen.getAllByRole('button')).toHaveLength(1)
    expect(submitButton()).toBeInTheDocument()
  })
})

describe('choosing a handle', () => {
  test('cannot continue while the field is empty', () => {
    render(<ChooseHandlePage />)

    expect(submitButton()).toBeDisabled()
  })

  test('enables continue once a handle is typed', () => {
    render(<ChooseHandlePage />)

    fireEvent.change(field(), { target: { value: 'chefanna' } })

    expect(submitButton()).toBeEnabled()
  })

  test('checks availability as the user types (UN-7)', async () => {
    render(<ChooseHandlePage />)

    fireEvent.change(field(), { target: { value: 'chefanna' } })

    await waitFor(() => expect(checkUsername).toHaveBeenCalledWith('chefanna'))
  })

  // Intended behaviour. It runs against a mocked API because the confirming
  // endpoint is not built yet; see the page's own note.
  test('confirms the normalised handle and reloads the account', async () => {
    render(<ChooseHandlePage />)

    fireEvent.change(field(), { target: { value: '  ChefAnna ' } })
    fireEvent.click(submitButton())

    await waitFor(() => expect(confirmUsername).toHaveBeenCalledWith('chefanna'))
    await waitFor(() => expect(refreshUser).toHaveBeenCalledTimes(1))
  })

  test('shows a handle-specific error when the server refuses the handle', async () => {
    confirmUsername.mockRejectedValue(new Error('That username is taken'))
    render(<ChooseHandlePage />)

    fireEvent.change(field(), { target: { value: 'chefanna' } })
    fireEvent.click(submitButton())

    expect(await screen.findByRole('alert')).toHaveTextContent(/that username is taken/i)
    expect(refreshUser).not.toHaveBeenCalled()
  })

  // An error message must not become a second disclosure channel.
  test('keeps the email out of a failure message', async () => {
    confirmUsername.mockRejectedValue(new Error('Something went wrong'))
    render(<ChooseHandlePage />)

    fireEvent.change(field(), { target: { value: 'chefanna' } })
    fireEvent.click(submitButton())

    await screen.findByRole('alert')
    expect(document.body.innerHTML).not.toContain(EMAIL)
    expect(document.body.innerHTML).not.toContain(PROVISIONAL)
  })
})
