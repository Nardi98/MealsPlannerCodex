/**
 * @vitest-environment jsdom
 */
import { render, screen, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
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
import { stubViewport } from '../test/stubViewport'

const CONFIRMED = { email: 'demo@x.test', username: 'demo', username_confirmed: true }
// The counterpart of CONFIRMED. Extracted because the UN-11 assertions check
// that neither the handle nor the address it was derived from is rendered, and
// five hand-copied literals that must stay byte-identical for those assertions
// to mean anything is exactly the kind of thing that quietly stops meaning
// anything.
const UNCONFIRMED = {
  email: 'anna.rossi@x.test',
  username: 'anna_rossi',
  username_confirmed: false,
}

function signedIn(user) {
  authState = { user, loading: false, logout: vi.fn() }
}

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
  signedIn(CONFIRMED)
  render(<App />)
  expect(screen.getByText('recipes-page')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: /account menu/i })).toBeInTheDocument()
  expect(screen.queryByText('login-screen')).not.toBeInTheDocument()
})

test('offers Shared with me in the sidebar navigation', () => {
  signedIn(CONFIRMED)
  render(<App />)
  expect(screen.getByRole('button', { name: /shared with me/i })).toBeInTheDocument()
})

test('routes /shared-with-me to the shared-with-me page', () => {
  signedIn(CONFIRMED)
  visit('/shared-with-me')
  render(<App />)
  expect(screen.getByText('shared-with-me-page')).toBeInTheDocument()
})

test('routes /shared/:token to the shared recipe landing page', () => {
  signedIn(CONFIRMED)
  visit('/shared/abc123')
  render(<App />)
  expect(screen.getByText('shared-recipe-page')).toBeInTheDocument()
})

test('sends an unconfirmed handle to the choose-handle page', () => {
  signedIn(UNCONFIRMED)
  render(<App />)
  expect(screen.getByText('choose-handle-page')).toBeInTheDocument()
  expect(screen.queryByText('recipes-page')).not.toBeInTheDocument()
})

test.each(['/', '/recipes', '/meal-plan', '/ingredients', '/shopping-list', '/import-export', '/shared-with-me', '/shared/tok', '/anything-else'])(
  'an unconfirmed handle cannot reach %s',
  (path) => {
    signedIn(UNCONFIRMED)
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
  signedIn({ email: 'demo@x.test' })
  render(<App />)
  expect(screen.getByText('choose-handle-page')).toBeInTheDocument()
  expect(screen.queryByText('recipes-page')).not.toBeInTheDocument()
})

test('the provisional handle is never rendered before confirmation (UN-11)', () => {
  signedIn(UNCONFIRMED)
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
  signedIn(CONFIRMED)
  visit('/shared/tok-abc')
  render(<App />)

  expect(screen.getByText('shared-recipe-page')).toBeInTheDocument()
  expect(screen.queryByText('recipes-page')).not.toBeInTheDocument()
})

test('signing in with ?next=/s/<token> returns to the share, not the recipe list', () => {
  signedIn(CONFIRMED)
  visit('/login?next=/s/tok-abc')
  render(<App />)

  expect(screen.getByText('shared-recipe-page')).toBeInTheDocument()
  expect(window.location.pathname).toBe('/shared/tok-abc')
})

test('an encoded next parameter is honoured just as an unencoded one is', () => {
  signedIn(CONFIRMED)
  visit('/login?next=%2Fs%2Ftok-abc')
  render(<App />)

  expect(screen.getByText('shared-recipe-page')).toBeInTheDocument()
})

test('a next parameter pointing at another in-app page is honoured', () => {
  signedIn(CONFIRMED)
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
  signedIn(CONFIRMED)
  visit(path)
  render(<App />)

  // The fallback, and — the part that matters — the browser is still here.
  expect(screen.getByText('recipes-page')).toBeInTheDocument()
  expect(window.location.pathname).toBe('/recipes')
  expect(window.location.href).not.toMatch(/evil\.example/)
})

test('signing in at /login with no next lands on the recipe list', () => {
  signedIn(CONFIRMED)
  visit('/login')
  render(<App />)

  expect(screen.getByText('recipes-page')).toBeInTheDocument()
  expect(window.location.pathname).toBe('/recipes')
})

test('an unconfirmed handle still cannot be routed past the gate by next', () => {
  // UN-11 outranks SH-23: the handle gate is not a page you can be redirected
  // around, so a `next` must not become a way to reach the shell with an
  // unconfirmed, email-derived handle still in place.
  signedIn(UNCONFIRMED)
  visit('/login?next=/s/tok-abc')
  render(<App />)

  expect(screen.getByText('choose-handle-page')).toBeInTheDocument()
  expect(screen.queryByText('shared-recipe-page')).not.toBeInTheDocument()
})

// --- Mobile shell -----------------------------------------------------------
//
// jsdom does not evaluate media queries, so the shell branches on `useIsMobile`
// (which reads `matchMedia`) rather than on `md:` classes alone wherever the
// *markup* has to differ. Stubbing `matchMedia` is therefore how a viewport is
// chosen in these tests.

test('offers a menu button on mobile that opens the navigation drawer', async () => {
  stubViewport(true)
  signedIn(CONFIRMED)
  render(<App />)

  const burger = screen.getByRole('button', { name: /open menu/i })
  expect(screen.queryByRole('dialog', { name: /main navigation/i })).not.toBeInTheDocument()

  await userEvent.click(burger)
  expect(screen.getByRole('dialog', { name: /main navigation/i })).toBeInTheDocument()
  expect(burger).toHaveAttribute('aria-expanded', 'true')
})

test('keeps the account menu reachable on mobile', () => {
  // Regression: the header's action block was `hidden md:flex`, which left
  // phone users with no way to open preferences or log out at all.
  stubViewport(true)
  signedIn(CONFIRMED)
  render(<App />)

  const account = screen.getByRole('button', { name: /account menu/i })
  expect(account).toBeInTheDocument()
  // jsdom does not apply Tailwind, so presence in the DOM proves nothing about
  // visibility: assert instead that no ancestor is hidden below `md`.
  expect(account.closest('.hidden')).toBeNull()
})

test('shows no menu button on desktop', () => {
  stubViewport(false)
  signedIn(CONFIRMED)
  render(<App />)

  // Hidden by `md:hidden` rather than unmounted, so assert the class: jsdom
  // does not apply Tailwind, and a DOM-absence assertion would forbid that.
  expect(screen.getByRole('button', { name: /open menu/i })).toHaveClass('md:hidden')
  expect(screen.getByRole('button', { name: /shared with me/i })).toBeInTheDocument()
})
