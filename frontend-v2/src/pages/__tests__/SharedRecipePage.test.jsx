/**
 * @vitest-environment jsdom
 */
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, expect, test, vi } from 'vitest'
import '@testing-library/jest-dom/vitest'
import SharedRecipePage from '../SharedRecipePage'
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

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
  globalThis.localStorage.clear()
  globalThis.sessionStorage.clear()
})

function renderAt(path) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/shared/:token" element={<SharedRecipePage />} />
        <Route path="/shared" element={<SharedRecipePage />} />
      </Routes>
    </MemoryRouter>
  )
}

test('offers to copy the shared recipe rather than copying unprompted', async () => {
  renderAt('/shared/tok-123')

  expect(await screen.findByRole('button', { name: /copy to my book/i })).toBeInTheDocument()
  // The copy is a deliberate act (CP-1) and is rate-limited (CP-9); it must not
  // fire merely because the landing page was opened.
  expect(sharedWithMeApi.copyByToken).not.toHaveBeenCalled()
})

test('copies the recipe using the token from the URL', async () => {
  sharedWithMeApi.copyByToken.mockResolvedValue({
    id: 42,
    title: 'Ribollita',
    already_copied: false,
  })
  const user = userEvent.setup()

  renderAt('/shared/tok-123')
  await user.click(await screen.findByRole('button', { name: /copy to my book/i }))

  await waitFor(() =>
    expect(sharedWithMeApi.copyByToken).toHaveBeenCalledWith('tok-123')
  )
  expect(await screen.findByText(/ribollita.*added to your recipes/i)).toBeInTheDocument()
})

test('warns when the user already holds a copy (CP-11)', async () => {
  sharedWithMeApi.copyByToken.mockResolvedValue({
    id: 43,
    title: 'Ribollita',
    already_copied: true,
  })
  const user = userEvent.setup()

  renderAt('/shared/tok-123')
  await user.click(await screen.findByRole('button', { name: /copy to my book/i }))

  expect(await screen.findByText(/already had a copy/i)).toBeInTheDocument()
})

test('presents a 404 as a calm "no longer available", not an error', async () => {
  const gone = new Error('Not found')
  gone.status = 404
  sharedWithMeApi.copyByToken.mockRejectedValue(gone)
  const user = userEvent.setup()

  renderAt('/shared/revoked-token')
  await user.click(await screen.findByRole('button', { name: /copy to my book/i }))

  expect(await screen.findByText(/no longer available/i)).toBeInTheDocument()
  // SH-22: nothing about the recipe, its owner, or whether the token ever
  // existed may be inferred from the message.
  expect(screen.queryByText(/revoked-token/)).not.toBeInTheDocument()
})

test('explains a 403 as being signed in as the wrong account (SH-24)', async () => {
  const forbidden = new Error('This link was shared with a different account')
  forbidden.status = 403
  sharedWithMeApi.copyByToken.mockRejectedValue(forbidden)
  const user = userEvent.setup()

  renderAt('/shared/tok-123')
  await user.click(await screen.findByRole('button', { name: /copy to my book/i }))

  expect(await screen.findByRole('alert')).toHaveTextContent(/different account/i)
})

test('explains a 429 rate limit plainly (CP-9)', async () => {
  const limited = new Error('Rate limit exceeded')
  limited.status = 429
  sharedWithMeApi.copyByToken.mockRejectedValue(limited)
  const user = userEvent.setup()

  renderAt('/shared/tok-123')
  await user.click(await screen.findByRole('button', { name: /copy to my book/i }))

  expect(await screen.findByRole('alert')).toHaveTextContent(/too many|try again/i)
})

// The three below pin that the status, not the prose, decides. `client.js`
// attaches `error.status` to everything it throws, so the backend's wording is
// free to change, be translated, or be replaced by a generic proxy message
// without any of these outcomes silently degrading to "unknown error".

test('presents a 404 as gone even when the wording is not "not found"', async () => {
  const gone = new Error('Risorsa non disponibile')
  gone.status = 404
  sharedWithMeApi.copyByToken.mockRejectedValue(gone)
  const user = userEvent.setup()

  renderAt('/shared/tok-123')
  await user.click(await screen.findByRole('button', { name: /copy to my book/i }))

  expect(await screen.findByText(/no longer available/i)).toBeInTheDocument()
})

test('presents a 429 as a rate limit even when the wording does not say so', async () => {
  const limited = new Error('Troppe richieste')
  limited.status = 429
  sharedWithMeApi.copyByToken.mockRejectedValue(limited)
  const user = userEvent.setup()

  renderAt('/shared/tok-123')
  await user.click(await screen.findByRole('button', { name: /copy to my book/i }))

  expect(await screen.findByRole('alert')).toHaveTextContent(/too many|try again/i)
})

test('does not present a server error as gone just because it says "not found"', async () => {
  // The misfire prose-matching produces. A 500 mentioning "not found" — a
  // failed internal lookup, say — would be shown as the calm "this recipe is
  // gone" message, telling the user to stop trying when they should retry.
  const broken = new Error('Upstream dependency not found')
  broken.status = 500
  sharedWithMeApi.copyByToken.mockRejectedValue(broken)
  const user = userEvent.setup()

  renderAt('/shared/tok-123')
  await user.click(await screen.findByRole('button', { name: /copy to my book/i }))

  const alert = await screen.findByRole('alert')
  expect(alert).toHaveTextContent(/upstream dependency/i)
  expect(alert).not.toHaveTextContent(/no longer available/i)
})

test('says the link is malformed when the route carries no token', async () => {
  renderAt('/shared')

  expect(await screen.findByRole('alert')).toHaveTextContent(/missing its token/i)
  expect(
    screen.queryByRole('button', { name: /copy to my book/i })
  ).not.toBeInTheDocument()
})

test('never writes the share token to web storage', async () => {
  sharedWithMeApi.copyByToken.mockResolvedValue({
    id: 42,
    title: 'Ribollita',
    already_copied: false,
  })
  const user = userEvent.setup()

  renderAt('/shared/super-secret-token')
  await user.click(await screen.findByRole('button', { name: /copy to my book/i }))
  await screen.findByText(/added to your recipes/i)

  expect(globalThis.localStorage.length).toBe(0)
  expect(globalThis.sessionStorage.length).toBe(0)
})

test('does not display the raw token anywhere on the page', async () => {
  const { container } = renderAt('/shared/super-secret-token')
  await screen.findByRole('button', { name: /copy to my book/i })

  expect(container.textContent).not.toContain('super-secret-token')
})
