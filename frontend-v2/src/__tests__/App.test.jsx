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

import App from '../App'

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

test('shows the login screen when unauthenticated', () => {
  authState = { user: null, loading: false }
  render(<App />)
  expect(screen.getByText('login-screen')).toBeInTheDocument()
  expect(screen.queryByText('recipes-page')).not.toBeInTheDocument()
})

test('shows the app shell with a profile menu when authenticated', () => {
  authState = { user: { email: 'demo@x.test' }, loading: false, logout: vi.fn() }
  render(<App />)
  expect(screen.getByText('recipes-page')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: /account menu/i })).toBeInTheDocument()
  expect(screen.queryByText('login-screen')).not.toBeInTheDocument()
})

test('shows a loading state while hydrating the session', () => {
  authState = { user: null, loading: true }
  render(<App />)
  expect(screen.queryByText('login-screen')).not.toBeInTheDocument()
  expect(screen.queryByText('recipes-page')).not.toBeInTheDocument()
})
