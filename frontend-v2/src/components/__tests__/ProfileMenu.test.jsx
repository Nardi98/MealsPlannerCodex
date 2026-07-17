/**
 * @vitest-environment jsdom
 */
import { render, screen, fireEvent, cleanup } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import '@testing-library/jest-dom/vitest'
import ProfileMenu from '../ProfileMenu'

const logout = vi.fn()

vi.mock('../../auth/AuthContext', () => ({
  useAuth: () => ({ user: { email: 'demo@x.test', display_name: 'Demo User' }, logout }),
}))

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

test('is closed by default (email hidden until opened)', () => {
  render(<ProfileMenu />)
  expect(screen.queryByText('demo@x.test')).not.toBeInTheDocument()
})

test('opens on avatar click and shows the email', () => {
  render(<ProfileMenu />)
  fireEvent.click(screen.getByRole('button', { name: /account menu/i }))
  expect(screen.getByText('demo@x.test')).toBeInTheDocument()
})

test('calls logout when the Logout action is clicked', () => {
  render(<ProfileMenu />)
  fireEvent.click(screen.getByRole('button', { name: /account menu/i }))
  fireEvent.click(screen.getByRole('button', { name: /log out/i }))
  expect(logout).toHaveBeenCalledTimes(1)
})
