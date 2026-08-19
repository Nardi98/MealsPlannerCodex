/**
 * @vitest-environment jsdom
 */
import React from 'react'
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import '@testing-library/jest-dom/vitest'
import ShareRecipeModal from '../ShareRecipeModal'
import { sharesApi } from '../../api/sharesApi'

vi.mock('../../api/sharesApi', () => ({
  sharesApi: { create: vi.fn(), list: vi.fn(), revoke: vi.fn() },
}))

const recipe = { id: 7, title: 'Ribollita', image_url: '/img/ribollita.jpg' }

beforeEach(() => {
  sharesApi.create.mockReset()
  sharesApi.list.mockReset()
  sharesApi.revoke.mockReset()
  sharesApi.list.mockResolvedValue([])
})

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

function open(props = {}) {
  return render(<ShareRecipeModal recipe={recipe} open onClose={() => {}} {...props} />)
}

test('renders nothing when closed', () => {
  const { container } = render(
    <ShareRecipeModal recipe={recipe} open={false} onClose={() => {}} />
  )
  expect(container).toBeEmptyDOMElement()
})

// SH-7: the honest disclosure about link mode is a hard requirement.
test('states that anyone with the link can open the recipe', async () => {
  open()
  expect(
    await screen.findByText(/Anyone with the link can open this recipe/i)
  ).toBeInTheDocument()
})

// SH-7 again: naming a recipient must not be allowed to read as an access
// restriction, so the disclaimer is asserted verbatim.
test('says naming someone does not restrict who can open the link', async () => {
  open()
  expect(
    await screen.findByText(
      /so it appears in their Shared-with-me — it does not restrict who can open the link\./i
    )
  ).toBeInTheDocument()
})

// SH-8: modes are offered by effect, never by their internal names.
test('offers both modes in plain language, not by internal name', async () => {
  open()
  await screen.findByText(/Anyone with the link can open this recipe/i)
  expect(screen.getByText(/Only the person I name can open it/i)).toBeInTheDocument()
  expect(screen.queryByText(/^link$/i)).not.toBeInTheDocument()
  expect(screen.queryByText(/^person$/i)).not.toBeInTheDocument()
})

// SH-9: expiry is opt-in, with no default.
test('leaves expiry empty and says there is no expiry unless set', async () => {
  open()
  const expiry = await screen.findByLabelText(/expires/i)
  expect(expiry).toHaveValue('')
  expect(screen.getByText(/never expires unless you set a date/i)).toBeInTheDocument()
})

// Q-4: a photoless recipe unfurls badly when pasted into a chat app.
test('warns when the recipe has no photo', async () => {
  render(
    <ShareRecipeModal recipe={{ id: 8, title: 'Farro salad' }} open onClose={() => {}} />
  )
  expect(await screen.findByText(/bare text card/i)).toBeInTheDocument()
})

test('does not warn about unfurling when the recipe has a photo', async () => {
  open()
  await screen.findByText(/Anyone with the link can open this recipe/i)
  expect(screen.queryByText(/bare text card/i)).not.toBeInTheDocument()
})

test('creates a link share and shows the URL once, with a copy control', async () => {
  sharesApi.create.mockResolvedValue({
    id: 1,
    mode: 'link',
    url: 'https://app.test/shared/abc123',
    active: true,
  })
  open()
  fireEvent.click(await screen.findByRole('button', { name: /create share link/i }))

  await waitFor(() => expect(sharesApi.create).toHaveBeenCalled())
  expect(sharesApi.create).toHaveBeenCalledWith(7, {
    mode: 'link',
    recipient_email: '',
    expires_at: '',
  })
  expect(await screen.findByDisplayValue('https://app.test/shared/abc123')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: /copy link/i })).toBeInTheDocument()
  // The raw token is unrecoverable, so the UI must say the link is shown once.
  expect(screen.getByText(/shown once/i)).toBeInTheDocument()
})

test('passes the chosen recipient and expiry through to the API', async () => {
  sharesApi.create.mockResolvedValue({ id: 2, mode: 'person', url: 'https://app.test/shared/x' })
  open()
  fireEvent.click(await screen.findByLabelText(/Only the person I name can open it/i))
  fireEvent.change(screen.getByLabelText(/recipient email/i), {
    target: { value: 'chef@example.com' },
  })
  fireEvent.change(screen.getByLabelText(/expires/i), { target: { value: '2026-09-01' } })
  fireEvent.click(screen.getByRole('button', { name: /create share link/i }))

  await waitFor(() =>
    expect(sharesApi.create).toHaveBeenCalledWith(7, {
      mode: 'person',
      recipient_email: 'chef@example.com',
      expires_at: '2026-09-01',
    })
  )
})

// SH-5: a person-mode share without a recipient is meaningless.
test('refuses to create a person share with no recipient', async () => {
  open()
  fireEvent.click(await screen.findByLabelText(/Only the person I name can open it/i))
  fireEvent.click(screen.getByRole('button', { name: /create share link/i }))

  expect(await screen.findByText(/enter the email address/i)).toBeInTheDocument()
  expect(sharesApi.create).not.toHaveBeenCalled()
})

test('copies the link to the clipboard without logging it', async () => {
  const writeText = vi.fn(() => Promise.resolve())
  Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true })
  const logSpy = vi.spyOn(console, 'log').mockImplementation(() => {})
  sharesApi.create.mockResolvedValue({ id: 3, mode: 'link', url: 'https://app.test/shared/zz' })
  open()
  fireEvent.click(await screen.findByRole('button', { name: /create share link/i }))
  fireEvent.click(await screen.findByRole('button', { name: /copy link/i }))

  await waitFor(() => expect(writeText).toHaveBeenCalledWith('https://app.test/shared/zz'))
  expect(logSpy).not.toHaveBeenCalled()
})

// SH-11: a rate limit is recoverable, and must not read as a hard failure.
test('explains a 429 calmly instead of as a generic failure', async () => {
  const err = new Error('Too Many Requests')
  err.status = 429
  sharesApi.create.mockRejectedValue(err)
  open()
  fireEvent.click(await screen.findByRole('button', { name: /create share link/i }))

  expect(await screen.findByText(/created a lot of shares/i)).toBeInTheDocument()
})

test('shows the API error message when creation fails', async () => {
  sharesApi.create.mockRejectedValue(new Error('Recipe not found'))
  open()
  fireEvent.click(await screen.findByRole('button', { name: /create share link/i }))

  expect(await screen.findByText(/Recipe not found/)).toBeInTheDocument()
})

// SH-20: every existing share is listed with its details.
test('lists existing shares with mode, recipient, dates and expiry', async () => {
  sharesApi.list.mockResolvedValue([
    {
      id: 42,
      mode: 'person',
      recipient_email: 'chef@example.com',
      created_at: '2026-08-01T10:00:00Z',
      expires_at: '2026-09-01T10:00:00Z',
      last_viewed_at: '2026-08-05T10:00:00Z',
      revoked_at: null,
      active: true,
    },
  ])
  open()

  const row = (await screen.findByText(/chef@example\.com/)).closest('li')
  expect(row).toBeTruthy()
  expect(row).toHaveTextContent(/Only the person named can open it/i)
  expect(row).toHaveTextContent(/Created/i)
  expect(row).toHaveTextContent(/Last viewed/i)
  expect(row).toHaveTextContent(/Expires/i)
})

test('revokes a share and refreshes the list', async () => {
  sharesApi.list
    .mockResolvedValueOnce([
      { id: 42, mode: 'link', recipient_email: null, active: true, created_at: null },
    ])
    .mockResolvedValueOnce([])
  sharesApi.revoke.mockResolvedValue(null)
  open()

  fireEvent.click(await screen.findByRole('button', { name: /revoke/i }))

  await waitFor(() => expect(sharesApi.revoke).toHaveBeenCalledWith(42))
  await waitFor(() => expect(screen.queryByRole('button', { name: /revoke/i })).toBeNull())
})

// SH-20 listing shows revoked/expired shares as inactive rather than offering a
// revoke control that would do nothing.
test('does not offer a revoke control for an inactive share', async () => {
  sharesApi.list.mockResolvedValue([
    { id: 43, mode: 'link', active: false, revoked_at: '2026-08-02T10:00:00Z' },
  ])
  open()

  expect(await screen.findByText(/revoked/i)).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /^revoke$/i })).toBeNull()
})

// The URL is a bearer capability: it must not survive the dialog.
test('forgets the created URL when the dialog is closed and reopened', async () => {
  sharesApi.create.mockResolvedValue({ id: 4, mode: 'link', url: 'https://app.test/shared/secret' })
  const { rerender } = open()
  fireEvent.click(await screen.findByRole('button', { name: /create share link/i }))
  await screen.findByDisplayValue('https://app.test/shared/secret')

  rerender(<ShareRecipeModal recipe={recipe} open={false} onClose={() => {}} />)
  rerender(<ShareRecipeModal recipe={recipe} open onClose={() => {}} />)

  await waitFor(() =>
    expect(screen.queryByDisplayValue('https://app.test/shared/secret')).toBeNull()
  )
})
