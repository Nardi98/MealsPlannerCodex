/**
 * @vitest-environment jsdom
 */
import { render, screen, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import '@testing-library/jest-dom/vitest'
import { MemoryRouter, Routes, Route, useLocation } from 'react-router-dom'
import ViewModePill from '../ViewModePill'
import { ViewModeProvider, useViewMode } from '../../auth/ViewModeContext'

let authState

vi.mock('../../auth/AuthContext', () => ({
  useAuth: () => authState,
}))

afterEach(cleanup)

beforeEach(() => {
  authState = { user: { email: 'a@x.test', is_admin: true } }
})

// Reports where the router is and which mode is live, so one render can assert
// the pill's two jobs: flipping the mode and moving the user somewhere it means.
function Where() {
  const { pathname } = useLocation()
  const { mode } = useViewMode()
  return <div>{`${mode}@${pathname}`}</div>
}

function renderPill(initialPath = '/meal-plan') {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <ViewModeProvider>
        <ViewModePill />
        <Routes>
          <Route path="*" element={<Where />} />
        </Routes>
      </ViewModeProvider>
    </MemoryRouter>,
  )
}

test('a non-admin gets no pill at all', () => {
  authState = { user: { email: 'a@x.test', is_admin: false } }
  renderPill()

  expect(screen.queryByRole('button', { name: 'Admin' })).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'User' })).not.toBeInTheDocument()
})

test('an admin gets both segments, with User pressed', () => {
  renderPill()

  expect(screen.getByRole('button', { name: 'User' })).toHaveAttribute('aria-pressed', 'true')
  expect(screen.getByRole('button', { name: 'Admin' })).toHaveAttribute('aria-pressed', 'false')
})

test('switching to admin opens the library and marks the segment', async () => {
  renderPill('/meal-plan')

  await userEvent.click(screen.getByRole('button', { name: 'Admin' }))

  expect(screen.getByText('admin@/discover')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Admin' })).toHaveAttribute('aria-pressed', 'true')
})

test('switching back to user returns to the recipe book', async () => {
  renderPill('/meal-plan')
  await userEvent.click(screen.getByRole('button', { name: 'Admin' }))

  await userEvent.click(screen.getByRole('button', { name: 'User' }))

  expect(screen.getByText('user@/recipes')).toBeInTheDocument()
})
