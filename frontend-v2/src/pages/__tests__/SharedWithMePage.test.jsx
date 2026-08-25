/**
 * @vitest-environment jsdom
 */
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import '@testing-library/jest-dom/vitest'
import SharedWithMePage from '../SharedWithMePage'
import { sharedWithMeApi } from '../../api/sharedWithMeApi'

vi.mock('../../api/sharedWithMeApi', () => ({
  sharedWithMeApi: {
    fetchAll: vi.fn(),
    fetchOne: vi.fn(),
    copy: vi.fn(),
    dismiss: vi.fn(),
    copyByToken: vi.fn(),
  },
}))

function entry(overrides = {}, recipeOverrides = {}) {
  return {
    share_id: 7,
    mode: 'person',
    created_at: '2026-08-01T10:00:00',
    expires_at: null,
    ...overrides,
    recipe: {
      title: 'Ribollita',
      image_url: null,
      procedure: 'Simmer the kale with the bread.',
      ingredients: [
        { name: 'Kale', quantity: 200, unit: 'g' },
        { name: 'Stale bread', quantity: null, unit: null },
      ],
      tags: ['soup', 'winter'],
      course: 'main',
      author_display_name: 'Anna Rossi',
      author_username: 'anna',
      attribution: null,
      ...recipeOverrides,
    },
  }
}

beforeEach(() => {
  sharedWithMeApi.fetchAll.mockResolvedValue([])
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

// --- SWM-1: the list ---------------------------------------------------------

test('lists every recipe shared with the account', async () => {
  sharedWithMeApi.fetchAll.mockResolvedValue([entry()])

  render(<SharedWithMePage />)

  expect(await screen.findByText('Ribollita')).toBeInTheDocument()
  expect(screen.getByText(/@anna/)).toBeInTheDocument()
})

test('shows no serving count, because quantities are per person', async () => {
  sharedWithMeApi.fetchAll.mockResolvedValue([entry()])

  render(<SharedWithMePage />)
  await screen.findByText('Ribollita')

  expect(screen.queryByText(/Serves/i)).toBeNull()
})

test('says so plainly when nothing has been shared', async () => {
  render(<SharedWithMePage />)

  expect(await screen.findByText(/nothing has been shared with you/i)).toBeInTheDocument()
})

test('surfaces a load failure without losing the page', async () => {
  sharedWithMeApi.fetchAll.mockRejectedValue(new Error('Network down'))

  render(<SharedWithMePage />)

  expect(await screen.findByRole('alert')).toHaveTextContent(/network down/i)
})

// --- PRV-2: nothing outside the allowlist ------------------------------------

test('never renders fields outside the PRV-2 allowlist', async () => {
  sharedWithMeApi.fetchAll.mockResolvedValue([
    entry({}, {
      // A hostile / future payload carrying fields the page must ignore.
      id: 999,
      score: 8.5,
      bulk_prep: true,
      author_email: 'anna@example.com',
      user_id: 3,
    }),
  ])

  const { container } = render(<SharedWithMePage />)
  await screen.findByText('Ribollita')

  const text = container.textContent
  expect(text).not.toContain('anna@example.com')
  expect(text).not.toContain('8.5')
  expect(text).not.toContain('999')
})

// --- SWM-2: view + copy only -------------------------------------------------

test('opens a read-only detail view with the ingredients and procedure', async () => {
  sharedWithMeApi.fetchAll.mockResolvedValue([entry()])
  const user = userEvent.setup()

  render(<SharedWithMePage />)
  await user.click(await screen.findByRole('button', { name: /view ribollita/i }))

  expect(await screen.findByText(/simmer the kale/i)).toBeInTheDocument()
  expect(screen.getByText('Kale — 200 g')).toBeInTheDocument()
  expect(screen.getByText('Stale bread')).toBeInTheDocument()
  // SWM-2: view and copy are the only actions — nothing that edits.
  expect(screen.queryByRole('button', { name: /^edit$/i })).not.toBeInTheDocument()
  expect(screen.queryByRole('textbox')).not.toBeInTheDocument()
})

test('copies an entry into the user’s own book', async () => {
  sharedWithMeApi.fetchAll.mockResolvedValue([entry()])
  sharedWithMeApi.copy.mockResolvedValue({ id: 42, title: 'Ribollita', already_copied: false })
  const user = userEvent.setup()

  render(<SharedWithMePage />)
  await user.click(await screen.findByRole('button', { name: /view ribollita/i }))
  await user.click(await screen.findByRole('button', { name: /copy to my book/i }))

  await waitFor(() => expect(sharedWithMeApi.copy).toHaveBeenCalledWith(7))
  expect(await screen.findByText(/added to your recipes/i)).toBeInTheDocument()
})

test('warns when the user already holds a copy (CP-11)', async () => {
  sharedWithMeApi.fetchAll.mockResolvedValue([entry()])
  sharedWithMeApi.copy.mockResolvedValue({ id: 43, title: 'Ribollita', already_copied: true })
  const user = userEvent.setup()

  render(<SharedWithMePage />)
  await user.click(await screen.findByRole('button', { name: /view ribollita/i }))
  await user.click(await screen.findByRole('button', { name: /copy to my book/i }))

  expect(await screen.findByText(/already had a copy/i)).toBeInTheDocument()
})

test('presents a 404 on copy as a calm "no longer available", not an error', async () => {
  sharedWithMeApi.fetchAll.mockResolvedValue([entry()])
  const notFound = new Error('Not found')
  notFound.status = 404
  sharedWithMeApi.copy.mockRejectedValue(notFound)
  const user = userEvent.setup()

  render(<SharedWithMePage />)
  await user.click(await screen.findByRole('button', { name: /view ribollita/i }))
  await user.click(await screen.findByRole('button', { name: /copy to my book/i }))

  expect(await screen.findByText(/no longer available/i)).toBeInTheDocument()
})

test('presents a 404 as gone even when the wording is not "not found"', async () => {
  // The status is the contract; the prose is the backend's to reword or
  // translate. Matching on it made this outcome depend on an English string
  // nobody had promised to keep.
  sharedWithMeApi.fetchAll.mockResolvedValue([entry()])
  const gone = new Error('Risorsa non disponibile')
  gone.status = 404
  sharedWithMeApi.copy.mockRejectedValue(gone)
  const user = userEvent.setup()

  render(<SharedWithMePage />)
  await user.click(await screen.findByRole('button', { name: /view ribollita/i }))
  await user.click(await screen.findByRole('button', { name: /copy to my book/i }))

  expect(await screen.findByText(/no longer available/i)).toBeInTheDocument()
})

test('does not present a server error as gone just because it says "not found"', async () => {
  sharedWithMeApi.fetchAll.mockResolvedValue([entry()])
  const broken = new Error('Upstream dependency not found')
  broken.status = 500
  sharedWithMeApi.copy.mockRejectedValue(broken)
  const user = userEvent.setup()

  render(<SharedWithMePage />)
  await user.click(await screen.findByRole('button', { name: /view ribollita/i }))
  await user.click(await screen.findByRole('button', { name: /copy to my book/i }))

  expect(await screen.findByText(/upstream dependency/i)).toBeInTheDocument()
  expect(screen.queryByText(/no longer available/i)).not.toBeInTheDocument()
})

// --- SWM-3: dismiss ----------------------------------------------------------

test('dismisses an entry and drops it from the list', async () => {
  sharedWithMeApi.fetchAll.mockResolvedValue([entry()])
  sharedWithMeApi.dismiss.mockResolvedValue(null)
  const user = userEvent.setup()

  render(<SharedWithMePage />)
  await user.click(await screen.findByRole('button', { name: /dismiss ribollita/i }))

  await waitFor(() => expect(sharedWithMeApi.dismiss).toHaveBeenCalledWith(7))
  await waitFor(() => expect(screen.queryByText('Ribollita')).not.toBeInTheDocument())
})

// --- AT-3: attribution travels with the shared recipe ------------------------

test('shows the original credit when the shared recipe is itself a copy', async () => {
  sharedWithMeApi.fetchAll.mockResolvedValue([
    entry({}, {
      attribution: {
        author_username: 'bruno',
        recipe_title: 'Nonna’s ribollita',
        copied_at: '2026-07-01T09:00:00',
      },
    }),
  ])

  render(<SharedWithMePage />)

  expect(
    await screen.findByText('Adapted from Nonna’s ribollita by @bruno')
  ).toBeInTheDocument()
})

// --- security ----------------------------------------------------------------

test('renders author-controlled text as text, never as markup', async () => {
  sharedWithMeApi.fetchAll.mockResolvedValue([
    entry({}, {
      title: '<img src=x onerror="alert(1)">',
      author_display_name: '<script>alert(2)</script>',
    }),
  ])

  const { container } = render(<SharedWithMePage />)
  await screen.findByText('<img src=x onerror="alert(1)">')

  expect(container.querySelector('img')).toBeNull()
  expect(container.querySelector('script')).toBeNull()
})

test('writes nothing about the shares to web storage', async () => {
  globalThis.localStorage.clear()
  globalThis.sessionStorage.clear()
  sharedWithMeApi.fetchAll.mockResolvedValue([entry()])

  render(<SharedWithMePage />)
  await screen.findByText('Ribollita')

  expect(globalThis.localStorage.length).toBe(0)
  expect(globalThis.sessionStorage.length).toBe(0)
})
