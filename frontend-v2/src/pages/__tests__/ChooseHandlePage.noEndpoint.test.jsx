/**
 * @vitest-environment jsdom
 *
 * The state of the world as shipped: there is no endpoint that confirms a
 * handle. UN-8/UN-9 are deferred to Part 2, so `POST /auth/username` is
 * deliberately not built and `authApi` has no `confirmUsername`.
 *
 * A separate file because it needs `authApi` mocked *without* that method,
 * which the main suite's mock deliberately provides.
 */
import { render, screen, fireEvent, cleanup } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import '@testing-library/jest-dom/vitest'
import ChooseHandlePage from '../ChooseHandlePage'

const refreshUser = vi.fn()

vi.mock('../../auth/AuthContext', () => ({
  useAuth: () => ({
    user: { id: 7, email: 'anna.rossi@example.com', username: 'anna_rossi' },
    refreshUser,
  }),
}))

vi.mock('../../api/authApi', () => ({
  authApi: { checkUsername: vi.fn().mockResolvedValue({ available: true, reason: null }) },
}))

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

test('says plainly that the handle cannot be saved yet, instead of hanging', async () => {
  render(<ChooseHandlePage />)

  fireEvent.change(screen.getByLabelText(/username/i), { target: { value: 'chefanna' } })
  fireEvent.click(screen.getByRole('button', { name: /continue/i }))

  expect(await screen.findByRole('alert')).toHaveTextContent(/not available yet/i)
})

test('invents no request when there is no endpoint to call', () => {
  globalThis.fetch = vi.fn()
  render(<ChooseHandlePage />)

  fireEvent.change(screen.getByLabelText(/username/i), { target: { value: 'chefanna' } })
  fireEvent.click(screen.getByRole('button', { name: /continue/i }))

  expect(globalThis.fetch).not.toHaveBeenCalled()
  expect(refreshUser).not.toHaveBeenCalled()
})
