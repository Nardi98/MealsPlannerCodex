/**
 * @vitest-environment jsdom
 */
import { render, screen, cleanup } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import '@testing-library/jest-dom/vitest'

let authState

vi.mock('../auth/AuthContext', () => ({
  AuthProvider: ({ children }) => children,
  useAuth: () => authState,
}))
vi.mock('../pages/LoginPage', () => ({ default: () => <div>login-screen</div> }))
vi.mock('../pages/RecipesPage', () => ({ default: () => <div>recipes-page</div> }))
vi.mock('../pages/MealPlanPage', () => ({ default: () => <div>meal-plan-page</div> }))
vi.mock('../pages/IngredientsPage', () => ({ default: () => <div>ingredients-page</div> }))
vi.mock('../pages/ShoppingListPage', () => ({ default: () => <div>shopping-page</div> }))
vi.mock('../pages/ImportExportPage', () => ({ default: () => <div>import-page</div> }))
vi.mock('../pages/SharedWithMePage', () => ({ default: () => <div>shared-with-me-page</div> }))
vi.mock('../pages/SharedRecipePage', () => ({ default: () => <div>shared-recipe-page</div> }))
vi.mock('../pages/ChooseHandlePage', () => ({ default: () => <div>choose-handle-page</div> }))

import App from '../App'

const CONFIRMED = { email: 'demo@x.test', username: 'demo', username_confirmed: true }

function visit(path) {
  window.history.pushState({}, '', path)
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
  window.history.pushState({}, '', '/')
})

test('shows the login screen when unauthenticated', () => {
  authState = { user: null, loading: false }
  render(<App />)
  expect(screen.getByText('login-screen')).toBeInTheDocument()
  expect(screen.queryByText('recipes-page')).not.toBeInTheDocument()
})

test('shows the app shell with a profile menu when authenticated', () => {
  authState = { user: CONFIRMED, loading: false, logout: vi.fn() }
  render(<App />)
  expect(screen.getByText('recipes-page')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: /account menu/i })).toBeInTheDocument()
  expect(screen.queryByText('login-screen')).not.toBeInTheDocument()
})

test('offers Shared with me in the sidebar navigation', () => {
  authState = { user: CONFIRMED, loading: false, logout: vi.fn() }
  render(<App />)
  expect(screen.getByRole('button', { name: /shared with me/i })).toBeInTheDocument()
})

test('routes /shared-with-me to the shared-with-me page', () => {
  authState = { user: CONFIRMED, loading: false, logout: vi.fn() }
  visit('/shared-with-me')
  render(<App />)
  expect(screen.getByText('shared-with-me-page')).toBeInTheDocument()
})

test('routes /shared/:token to the shared recipe landing page', () => {
  authState = { user: CONFIRMED, loading: false, logout: vi.fn() }
  visit('/shared/abc123')
  render(<App />)
  expect(screen.getByText('shared-recipe-page')).toBeInTheDocument()
})

test('sends an unconfirmed handle to the choose-handle page', () => {
  authState = { user: { email: 'anna.rossi@x.test', username: 'anna_rossi', username_confirmed: false }, loading: false, logout: vi.fn() }
  render(<App />)
  expect(screen.getByText('choose-handle-page')).toBeInTheDocument()
  expect(screen.queryByText('recipes-page')).not.toBeInTheDocument()
})

test.each(['/', '/recipes', '/meal-plan', '/ingredients', '/shopping-list', '/import-export', '/shared-with-me', '/shared/tok', '/anything-else'])(
  'an unconfirmed handle cannot reach %s',
  (path) => {
    authState = { user: { email: 'anna.rossi@x.test', username: 'anna_rossi', username_confirmed: false }, loading: false, logout: vi.fn() }
    visit(path)
    render(<App />)
    expect(screen.getByText('choose-handle-page')).toBeInTheDocument()
    expect(screen.queryByText('recipes-page')).not.toBeInTheDocument()
    expect(screen.queryByText('shared-with-me-page')).not.toBeInTheDocument()
    expect(screen.queryByText('shared-recipe-page')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /account menu/i })).not.toBeInTheDocument()
  },
)

test('a user record missing username_confirmed is treated as unconfirmed (fail closed)', () => {
  authState = { user: { email: 'demo@x.test' }, loading: false, logout: vi.fn() }
  render(<App />)
  expect(screen.getByText('choose-handle-page')).toBeInTheDocument()
  expect(screen.queryByText('recipes-page')).not.toBeInTheDocument()
})

test('the provisional handle is never rendered before confirmation (UN-11)', () => {
  authState = { user: { email: 'anna.rossi@x.test', username: 'anna_rossi', username_confirmed: false }, loading: false, logout: vi.fn() }
  render(<App />)
  expect(document.body.textContent).not.toMatch(/anna_rossi/)
  expect(document.body.textContent).not.toMatch(/anna\.rossi@/)
})

test('shows a loading state while hydrating the session', () => {
  authState = { user: null, loading: true }
  render(<App />)
  expect(screen.queryByText('login-screen')).not.toBeInTheDocument()
  expect(screen.queryByText('recipes-page')).not.toBeInTheDocument()
})
