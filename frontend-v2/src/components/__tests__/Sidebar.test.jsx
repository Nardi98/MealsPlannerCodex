/**
 * @vitest-environment jsdom
 */
import { render, screen, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, test, vi } from 'vitest'
import '@testing-library/jest-dom/vitest'
import { MemoryRouter, Routes, Route, useLocation } from 'react-router-dom'
import Sidebar from '../Sidebar'

let viewMode

vi.mock('../../auth/ViewModeContext', () => ({
  useViewMode: () => viewMode,
}))

afterEach(cleanup)

const USER_NAV = [
  'Recipes',
  'Discover',
  'Meal Plan',
  'Shared with me',
  'Ingredients',
  'Shopping List',
  'Import/Export',
]

function Where() {
  return <div>{`at ${useLocation().pathname}`}</div>
}

function renderSidebar({ mode = 'user', ...props } = {}) {
  viewMode = { mode, isAdminMode: mode === 'admin' }
  return render(
    <MemoryRouter initialEntries={['/recipes']}>
      <Sidebar {...props} />
      <Routes>
        <Route path="*" element={<Where />} />
      </Routes>
    </MemoryRouter>,
  )
}

test('user mode lists the whole app', () => {
  renderSidebar()

  expect(screen.getAllByRole('button').map((b) => b.textContent)).toEqual(USER_NAV)
})

test('admin mode lists Discover alone', () => {
  renderSidebar({ mode: 'admin' })

  expect(screen.getAllByRole('button').map((b) => b.textContent)).toEqual(['Discover'])
})

test('a nav item navigates and tells the drawer to close', async () => {
  const onNavigate = vi.fn()
  renderSidebar({ onNavigate })

  await userEvent.click(screen.getByRole('button', { name: 'Meal Plan' }))

  expect(screen.getByText('at /meal-plan')).toBeInTheDocument()
  expect(onNavigate).toHaveBeenCalled()
})
