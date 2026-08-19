/**
 * @vitest-environment jsdom
 */
import React from 'react'
import { render, screen, fireEvent, cleanup, act } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'
import '@testing-library/jest-dom/vitest'
import UsernameField, { UsernameField as Named } from '../UsernameField'

const checkUsername = vi.fn()

vi.mock('../../api/authApi', () => ({
  authApi: { checkUsername: (...args) => checkUsername(...args) },
}))

// Longer than the component's debounce, so one tick of this settles any pending
// check without the test needing to know the exact interval.
const PAST_DEBOUNCE = 1000

beforeEach(() => {
  vi.useFakeTimers()
  checkUsername.mockResolvedValue({ available: true, reason: null })
})

afterEach(() => {
  vi.useRealTimers()
  cleanup()
  vi.clearAllMocks()
})

// Controlled component: the harness owns the value, exactly as the real callers
// do, so typing behaves the way it does in the form.
function Harness({ error, initial = '' }) {
  const [value, setValue] = React.useState(initial)
  return <UsernameField value={value} onChange={setValue} error={error} />
}

function renderField(props = {}) {
  return render(<Harness {...props} />)
}

function type(value) {
  fireEvent.change(screen.getByLabelText(/username/i), { target: { value } })
}

async function settle(ms = PAST_DEBOUNCE) {
  await act(async () => {
    vi.advanceTimersByTime(ms)
  })
}

describe('the frozen contract', () => {
  test('is exported both by name and as the default', () => {
    expect(Named).toBe(UsernameField)
  })

  test('gives onChange the raw string, not the DOM event', () => {
    const onChange = vi.fn()
    render(<UsernameField value="" onChange={onChange} error="" />)

    type('chefanna')

    expect(onChange).toHaveBeenCalledWith('chefanna')
  })

  test('renders the error prop in an alert', () => {
    render(<UsernameField value="" onChange={() => {}} error="That username is taken" />)

    expect(screen.getByRole('alert')).toHaveTextContent('That username is taken')
  })
})

describe('debounced availability checking (UN-5 / UN-7)', () => {
  test('does not fire a request on every keystroke', async () => {
    renderField()

    type('c')
    type('ch')
    type('che')
    type('chef')
    expect(checkUsername).not.toHaveBeenCalled()

    await settle()

    expect(checkUsername).toHaveBeenCalledTimes(1)
    expect(checkUsername).toHaveBeenCalledWith('chef')
  })

  test('waits at least 300ms before asking the server', async () => {
    renderField()

    type('chefanna')
    await settle(299)

    expect(checkUsername).not.toHaveBeenCalled()
  })

  test('sends the normalised handle, not the raw input', async () => {
    renderField()

    type('  ChefAnna  ')
    await settle()

    expect(checkUsername).toHaveBeenCalledWith('chefanna')
  })

  test('never asks about a handle shorter than the minimum', async () => {
    renderField()

    type('ab')
    await settle()

    expect(checkUsername).not.toHaveBeenCalled()
  })

  test('says nothing at all until the user has typed something', async () => {
    renderField()
    await settle()

    expect(checkUsername).not.toHaveBeenCalled()
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })

  test('confirms a free handle', async () => {
    checkUsername.mockResolvedValue({ available: true, reason: null })
    renderField()

    type('chefanna')
    await settle()

    expect(screen.getByRole('status')).toHaveTextContent(/available/i)
  })

  test('reports a taken handle in words, not as the raw code', async () => {
    checkUsername.mockResolvedValue({ available: false, reason: 'taken' })
    renderField()

    type('chefanna')
    await settle()

    const status = screen.getByRole('status')
    expect(status).toHaveTextContent(/already taken/i)
    expect(status).not.toHaveTextContent(/^taken$/)
  })

  test('reports a reserved handle without revealing that it is reserved', async () => {
    checkUsername.mockResolvedValue({ available: false, reason: 'reserved' })
    renderField()

    type('support')
    await settle()

    expect(screen.getByRole('status')).toHaveTextContent(/is not available/i)
  })

  test("shows the server's validation message verbatim", async () => {
    checkUsername.mockResolvedValue({
      available: false,
      reason: 'Usernames cannot contain two underscores in a row',
    })
    renderField()

    type('chef__anna')
    await settle()

    expect(screen.getByRole('status')).toHaveTextContent(
      'Usernames cannot contain two underscores in a row'
    )
  })

  // The reason is server-relayed, user-controlled text. React escapes it; this
  // pins that it is never treated as markup.
  test('escapes markup in a server reason instead of rendering it', async () => {
    checkUsername.mockResolvedValue({
      available: false,
      reason: '<img src=x onerror=alert(1)>',
    })
    renderField()

    type('chefanna')
    await settle()

    expect(screen.getByRole('status')).toHaveTextContent('<img src=x onerror=alert(1)>')
    expect(document.querySelector('img')).toBeNull()
  })
})

describe('failure handling (UN-7)', () => {
  test('degrades to a soft notice when the rate limit is hit', async () => {
    // A 429 as `client.js` actually throws it: the status is what identifies
    // the outcome, and the field reads that rather than the message text, so
    // the backend is free to reword or translate it.
    const limited = new Error('Rate limit exceeded: 30 per 1 minute')
    limited.status = 429
    checkUsername.mockRejectedValue(limited)
    renderField()

    type('chefanna')
    await settle()

    const status = screen.getByRole('status')
    expect(status).toHaveTextContent(/too many/i)
    // A throttled check is not a rejection of the handle.
    expect(status).not.toHaveTextContent(/taken/i)
  })

  test('degrades to a soft notice when the check fails for any other reason', async () => {
    checkUsername.mockRejectedValue(new Error('Failed to fetch'))
    renderField()

    type('chefanna')
    await settle()

    expect(screen.getByRole('status')).toHaveTextContent(/could not check/i)
  })

  test('ignores a slow answer for a handle the user has moved on from', async () => {
    const resolvers = []
    checkUsername.mockImplementation(
      () => new Promise((resolve) => resolvers.push(resolve))
    )
    renderField()

    type('firsthandle')
    await settle()
    type('secondhandle')
    await settle()
    expect(resolvers).toHaveLength(2)

    // The second answer lands first, then the stale first one arrives.
    await act(async () => {
      resolvers[1]({ available: true, reason: null })
      resolvers[0]({ available: false, reason: 'taken' })
    })

    expect(screen.getByRole('status')).toHaveTextContent(/available/i)
  })
})
