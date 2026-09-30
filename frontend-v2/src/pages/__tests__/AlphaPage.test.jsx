/**
 * @vitest-environment jsdom
 */
// ALPHA-GATE: tests for the closed-alpha allowlist screen. Deleted whole with
// the alpha (docs/superpowers/specs/2026-09-30-alpha-allowlist-design.md).
import { render, screen, fireEvent, waitFor, within, cleanup } from '@testing-library/react'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import '@testing-library/jest-dom/vitest'
import AlphaPage from '../AlphaPage'
import { alphaApi } from '../../api/alphaApi'
import { stubViewport } from '../../test/stubViewport'

// Only the network calls are mocked. `importOriginal` keeps the module's own
// shape, so a renamed method here fails loudly rather than silently becoming a
// fresh `vi.fn()`.
vi.mock('../../api/alphaApi', async (importOriginal) => ({
  ...(await importOriginal()),
  alphaApi: {
    list: vi.fn(),
    add: vi.fn(),
    updateNote: vi.fn(),
    remove: vi.fn(),
  },
}))

stubViewport(false)

const INVITES = [
  {
    id: 3,
    email: 'newest@example.com',
    note: null,
    created_at: '2026-09-28T09:00:00',
    signed_up: false,
    signed_up_at: null,
  },
  {
    id: 2,
    email: 'friend@mealplanner.test',
    note: 'the friend account',
    created_at: '2026-09-20T09:00:00',
    signed_up: true,
    signed_up_at: '2026-09-21T09:00:00',
  },
  {
    id: 1,
    email: 'demo@mealplanner.test',
    note: null,
    created_at: '2026-09-10T09:00:00',
    signed_up: true,
    signed_up_at: '2026-09-11T09:00:00',
  },
]

// The page formats dates with the runner's own locale, so the expectation is
// built the same way rather than pinned to one country's order.
const shownDate = (iso) =>
  new Date(iso).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' })

beforeEach(() => {
  globalThis.fetch = vi.fn(() => Promise.reject(new Error('no network in tests')))
  alphaApi.list.mockResolvedValue(INVITES)
  alphaApi.add.mockResolvedValue({ added: [], skipped_duplicates: [], invalid: [] })
  alphaApi.updateNote.mockImplementation((id, note) => Promise.resolve({ ...INVITES[1], id, note }))
  alphaApi.remove.mockResolvedValue(null)
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

const inviteList = () => screen.findByRole('list', { name: 'Invited addresses' })
const rowFor = async (email) => within(await inviteList()).getByText(email).closest('li')
const textarea = () => screen.getByLabelText('Email addresses to invite')
const addButton = () => screen.getByRole('button', { name: 'Add invites' })

async function renderLoaded() {
  render(<AlphaPage />)
  await screen.findByText('demo@mealplanner.test')
}

test('the header counts the invites and how many became accounts', async () => {
  await renderLoaded()

  expect(screen.getByText(/3 invited/)).toBeInTheDocument()
  expect(screen.getByText(/2 signed up/)).toBeInTheDocument()
})

test('each row shows the address verbatim, its status badge and when it was added', async () => {
  await renderLoaded()

  const claimed = await rowFor('friend@mealplanner.test')
  expect(claimed).toHaveTextContent('Signed up')
  expect(claimed).toHaveTextContent('the friend account')

  const unclaimed = await rowFor('newest@example.com')
  expect(unclaimed).toHaveTextContent('Invited')
  expect(unclaimed).not.toHaveTextContent('Signed up')
  expect(unclaimed).toHaveTextContent(shownDate('2026-09-28T09:00:00'))
})

test('an empty list warns that signup is open to everyone', async () => {
  alphaApi.list.mockResolvedValue([])
  render(<AlphaPage />)

  const warning = await screen.findByRole('alert')
  expect(warning).toHaveTextContent(/open to everyone/i)
})

test('adding invites sends the pasted text, reports the outcome and clears the box', async () => {
  alphaApi.add.mockResolvedValue({
    added: ['a@x.com'],
    skipped_duplicates: ['b@x.com'],
    invalid: ['oops'],
  })
  await renderLoaded()

  fireEvent.change(textarea(), { target: { value: 'a@x.com, b@x.com\noops' } })
  fireEvent.click(addButton())

  await waitFor(() => expect(alphaApi.add).toHaveBeenCalledWith('a@x.com, b@x.com\noops'))
  const summary = await screen.findByRole('status')
  expect(summary).toHaveTextContent('a@x.com')
  expect(summary).toHaveTextContent('b@x.com')
  expect(summary).toHaveTextContent('oops')
  expect(textarea()).toHaveValue('')
  expect(alphaApi.list).toHaveBeenCalledTimes(2)
})

test('a failed add is announced and the typed addresses are kept', async () => {
  alphaApi.add.mockRejectedValue(new Error('Service unavailable'))
  await renderLoaded()

  fireEvent.change(textarea(), { target: { value: 'a@x.com' } })
  fireEvent.click(addButton())

  const problem = await screen.findByRole('alert')
  expect(problem).toHaveTextContent(/Service unavailable/)
  expect(textarea()).toHaveValue('a@x.com')
})

test('a note is edited in place and saved', async () => {
  await renderLoaded()

  const row = await rowFor('newest@example.com')
  fireEvent.click(within(row).getByRole('button', { name: 'Edit note' }))
  fireEvent.change(within(row).getByLabelText('Note for newest@example.com'), {
    target: { value: 'a tester' },
  })
  fireEvent.click(within(row).getByRole('button', { name: 'Save note' }))

  await waitFor(() => expect(alphaApi.updateNote).toHaveBeenCalledWith(3, 'a tester'))
  await waitFor(() => expect(alphaApi.list).toHaveBeenCalledTimes(2))
})

test('deleting asks first, and says plainly that the account is left alone', async () => {
  await renderLoaded()

  const row = await rowFor('friend@mealplanner.test')
  fireEvent.click(within(row).getByRole('button', { name: 'Delete' }))

  const dialog = await screen.findByRole('dialog')
  expect(dialog).toHaveTextContent(/does not remove an existing account/i)

  fireEvent.click(within(dialog).getByRole('button', { name: /Delete invite/i }))

  await waitFor(() => expect(alphaApi.remove).toHaveBeenCalledWith(2))
  await waitFor(() => expect(alphaApi.list).toHaveBeenCalledTimes(2))
})

test('cancelling the delete confirmation removes nothing', async () => {
  await renderLoaded()

  const row = await rowFor('friend@mealplanner.test')
  fireEvent.click(within(row).getByRole('button', { name: 'Delete' }))
  fireEvent.click(within(await screen.findByRole('dialog')).getByRole('button', { name: 'Cancel' }))

  await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
  expect(alphaApi.remove).not.toHaveBeenCalled()
})

test('a failed first load says so instead of rendering a blank page', async () => {
  alphaApi.list.mockRejectedValue(new Error('nope'))
  render(<AlphaPage />)

  expect(await screen.findByRole('alert')).toHaveTextContent(/Couldn’t load the alpha invites|Couldn't load the alpha invites/)
  expect(screen.getByRole('button', { name: 'Try again' })).toBeInTheDocument()
})
