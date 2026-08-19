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

// ---------------------------------------------------------------------------
// SH-23: return to the share URL after signing in
// ---------------------------------------------------------------------------
//
// Two ways a visitor arrives holding a share destination they have not reached
// yet, and both used to lose it:
//
//   1. `/shared/<token>` directly, signed out. The Gate renders the login
//      screen at that URL, so the destination survives in the address bar and
//      the shell picks it up once `user` appears. Pinned below because it is
//      load-bearing and invisible — nothing in the code says so.
//   2. `/login?next=/s/<token>`, which is where the server-rendered person-mode
//      share page sends an anonymous visitor. `/login` matches no route in the
//      shell, so signing in used to land on a blank page with the token gone.
//
// `next` is attacker-controlled; `nextDestination` owns the validation and is
// tested exhaustively next door. These tests are about the *routing*: that a
// legitimate destination is honoured and a hostile one is never navigated to.

test('an unauthenticated visitor to a share link sees login without losing the url', () => {
  authState = { user: null, loading: false }
  visit('/shared/tok-abc')
  render(<App />)

  expect(screen.getByText('login-screen')).toBeInTheDocument()
  expect(window.location.pathname).toBe('/shared/tok-abc')
})

test('signing in at a share url lands on the shared recipe, not the recipe list', () => {
  authState = { user: CONFIRMED, loading: false, logout: vi.fn() }
  visit('/shared/tok-abc')
  render(<App />)

  expect(screen.getByText('shared-recipe-page')).toBeInTheDocument()
  expect(screen.queryByText('recipes-page')).not.toBeInTheDocument()
})

test('signing in with ?next=/s/<token> returns to the share, not the recipe list', () => {
  authState = { user: CONFIRMED, loading: false, logout: vi.fn() }
  visit('/login?next=/s/tok-abc')
  render(<App />)

  expect(screen.getByText('shared-recipe-page')).toBeInTheDocument()
  expect(window.location.pathname).toBe('/shared/tok-abc')
})

test('an encoded next parameter is honoured just as an unencoded one is', () => {
  authState = { user: CONFIRMED, loading: false, logout: vi.fn() }
  visit('/login?next=%2Fs%2Ftok-abc')
  render(<App />)

  expect(screen.getByText('shared-recipe-page')).toBeInTheDocument()
})

test('a next parameter pointing at another in-app page is honoured', () => {
  authState = { user: CONFIRMED, loading: false, logout: vi.fn() }
  visit('/login?next=/shared-with-me')
  render(<App />)

  expect(screen.getByText('shared-with-me-page')).toBeInTheDocument()
})

test.each([
  ['an absolute url', '/login?next=https%3A%2F%2Fevil.example'],
  ['a protocol-relative url', '/login?next=%2F%2Fevil.example'],
  ['a backslash authority', '/login?next=%2F%5Cevil.example'],
  ['a javascript url', '/login?next=javascript%3Aalert(1)'],
  ['an encoded protocol-relative url', '/login?next=%2F%252f%252fevil.example'],
])('a hostile next (%s) is ignored and falls back to the recipe list', (_name, path) => {
  authState = { user: CONFIRMED, loading: false, logout: vi.fn() }
  visit(path)
  render(<App />)

  // The fallback, and — the part that matters — the browser is still here.
  expect(screen.getByText('recipes-page')).toBeInTheDocument()
  expect(window.location.pathname).toBe('/recipes')
  expect(window.location.href).not.toMatch(/evil\.example/)
})

test('signing in at /login with no next lands on the recipe list', () => {
  authState = { user: CONFIRMED, loading: false, logout: vi.fn() }
  visit('/login')
  render(<App />)

  expect(screen.getByText('recipes-page')).toBeInTheDocument()
  expect(window.location.pathname).toBe('/recipes')
})

test('an unconfirmed handle still cannot be routed past the gate by next', () => {
  // UN-11 outranks SH-23: the handle gate is not a page you can be redirected
  // around, so a `next` must not become a way to reach the shell with an
  // unconfirmed, email-derived handle still in place.
  authState = {
    user: { email: 'anna.rossi@x.test', username: 'anna_rossi', username_confirmed: false },
    loading: false,
    logout: vi.fn(),
  }
  visit('/login?next=/s/tok-abc')
  render(<App />)

  expect(screen.getByText('choose-handle-page')).toBeInTheDocument()
  expect(screen.queryByText('shared-recipe-page')).not.toBeInTheDocument()
})
