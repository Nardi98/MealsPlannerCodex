import React from 'react'
import { BrowserRouter, Routes, Route, useLocation, useNavigate } from 'react-router-dom'
import {
  CalendarDaysIcon,
  BookmarkIcon,
  ShoppingCartIcon,
  BeakerIcon,
  ArrowUpTrayIcon,
  InboxArrowDownIcon,
} from '@heroicons/react/24/outline'
import { Input, ProfileMenu } from './components'
import RecipesPage from './pages/RecipesPage'
import MealPlanPage from './pages/MealPlanPage'
import IngredientsPage from './pages/IngredientsPage'
import ShoppingListPage from './pages/ShoppingListPage'
import ImportExportPage from './pages/ImportExportPage'
import LoginPage from './pages/LoginPage'
import VerifyEmailPage from './pages/VerifyEmailPage'
import ForgotPasswordPage from './pages/ForgotPasswordPage'
import ResetPasswordPage from './pages/ResetPasswordPage'
import SharedWithMePage from './pages/SharedWithMePage'
import SharedRecipePage from './pages/SharedRecipePage'
import ChooseHandlePage from './pages/ChooseHandlePage'
import { AuthProvider, useAuth } from './auth/AuthContext'
import { nextFromSearch } from './auth/nextDestination'

// Where a freshly-authenticated user goes when nothing better is known.
const DEFAULT_LANDING = '/recipes'

// Paths the shell has no route for, so arriving at one authenticated must be
// resolved to somewhere real rather than rendering an empty <main>. `/login` is
// the one that matters: the server-rendered share page sends anonymous visitors
// to `/login?next=/s/<token>`, and until this existed they signed in and landed
// on a blank page with the token discarded (SH-23).
const NON_SHELL_PATHS = ['/login', '/verify-email', '/forgot-password', '/reset-password']

const NAV = [
  { label: 'Recipes', path: '/recipes', Icon: BookmarkIcon, color: 'var(--cat-berry)', match: (p) => p === '/' || p === '/recipes' },
  { label: 'Meal Plan', path: '/meal-plan', Icon: CalendarDaysIcon, color: 'var(--c-a2)', match: (p) => p === '/meal-plan' },
  { label: 'Shared with me', path: '/shared-with-me', Icon: InboxArrowDownIcon, color: 'var(--cat-sky)', match: (p) => p === '/shared-with-me' },
  { label: 'Ingredients', path: '/ingredients', Icon: BeakerIcon, color: 'var(--cat-olive)', match: (p) => p === '/ingredients' },
  { label: 'Shopping List', path: '/shopping-list', Icon: ShoppingCartIcon, color: 'var(--cat-teal)', match: (p) => p === '/shopping-list' },
  { label: 'Import/Export', path: '/import-export', Icon: ArrowUpTrayIcon, color: 'var(--cat-plum)', match: (p) => p === '/import-export' },
]

function Sidebar() {
  const navigate = useNavigate()
  const location = useLocation()

  return (
    <div
      className="flex flex-col gap-1"
      style={{
        background: 'var(--surface-sidebar)',
        borderRadius: 'var(--radius-lg)',
        boxShadow: 'var(--shadow-md)',
        padding: 12,
        width: 'var(--sidebar-width)',
        height: '100%',
        boxSizing: 'border-box',
      }}
    >
      {NAV.map((item) => {
        const { label, path, color, match } = item
        const NavIcon = item.Icon
        const active = match(location.pathname)
        return (
          <button
            key={label}
            type="button"
            onClick={() => navigate(path)}
            className="flex items-center gap-3 text-left"
            style={{
              padding: '11px 12px',
              borderRadius: 'var(--radius-md)',
              border: 'none',
              cursor: 'pointer',
              width: '100%',
              background: active ? 'rgba(255,255,255,0.16)' : 'transparent',
            }}
          >
            <NavIcon className="h-5 w-5" style={{ color }} />
            <span
              style={{
                fontFamily: 'var(--font-display)',
                fontWeight: 'var(--weight-medium)',
                fontSize: 14,
                color: 'var(--text-on-dark)',
              }}
            >
              {label}
            </span>
          </button>
        )
      })}
    </div>
  )
}

// SH-23. Consumes a `?next=` destination once, on the render that first shows
// the shell — which is the render immediately after sign-in.
//
// It runs *inside* the authenticated branch on purpose. The gate above it
// (`username_confirmed`) is not a page a redirect may skip, so an unconfirmed
// account never reaches this component and a `next` cannot be used to route
// around handle selection (UN-11).
//
// `replace: true` so the consumed `/login?next=…` does not sit in history: the
// back button should return the user to wherever they came from, not to a
// sign-in URL that now redirects them forward again.
function ReturnToNext() {
  const location = useLocation()
  const navigate = useNavigate()

  React.useEffect(() => {
    const destination = nextFromSearch(location.search)
    if (destination) {
      navigate(destination, { replace: true })
      return
    }
    // No usable destination — either none was given, or it was rejected as
    // hostile. Either way an unroutable path must not be left on screen as a
    // blank shell. A rejected `next` is deliberately indistinguishable from an
    // absent one: there is nothing useful to tell the user, and naming the
    // refusal would only confirm to an attacker which shapes are filtered.
    if (NON_SHELL_PATHS.includes(location.pathname)) {
      navigate(DEFAULT_LANDING, { replace: true })
    }
    // Mount-only: this consumes an arrival, not every later navigation. Re-
    // running it on each location change would make `?next=` sticky and fight
    // the user's own clicks.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return null
}

function Shell() {
  const rowRef = React.useRef(null)
  const wrapRef = React.useRef(null)

  React.useEffect(() => {
    const update = () => {
      if (!rowRef.current || !wrapRef.current) return
      // Bottom stays pinned to the viewport bottom (20px gutter); the top rises
      // with scroll until it reaches the top gutter — so the sidebar grows.
      const topVp = rowRef.current.getBoundingClientRect().top
      const desiredTop = Math.max(20, topVp)
      wrapRef.current.style.height = `${Math.max(0, window.innerHeight - 20 - desiredTop)}px`
    }
    update()
    window.addEventListener('scroll', update, { passive: true })
    window.addEventListener('resize', update)
    return () => {
      window.removeEventListener('scroll', update)
      window.removeEventListener('resize', update)
    }
  }, [])

  return (
    <div style={{ minHeight: '100vh', boxSizing: 'border-box', padding: 20 }}>
      <header
        className="flex items-center justify-between"
        style={{ padding: '4px 8px 18px 24px' }}
      >
        <img
          src="/assets/Logo_mealplanner.png"
          alt="Meal Planner logo"
          style={{ height: 52, opacity: 0.9 }}
        />
        <div className="hidden md:flex items-center gap-3">
          <Input placeholder="Search…" style={{ width: 220 }} />
          <ProfileMenu />
        </div>
      </header>

      <div
        style={{
          height: 1,
          margin: '0 8px 20px',
          background:
            'linear-gradient(to right, transparent, color-mix(in srgb, var(--c-pos) 22%, transparent) 12%, color-mix(in srgb, var(--c-pos) 22%, transparent) 88%, transparent)',
        }}
      />

      <div ref={rowRef} className="flex flex-col gap-5 md:flex-row md:items-start">
        <div
          ref={wrapRef}
          className="flex-shrink-0 sticky top-5 overflow-hidden"
          style={{ alignSelf: 'flex-start' }}
        >
          <Sidebar />
        </div>
        <div
          className="min-w-0 flex-1"
          style={{
            background: 'var(--surface-page)',
            borderRadius: 'var(--radius-lg)',
            boxShadow: 'var(--shadow-lg)',
            border: '1px solid var(--border-default)',
          }}
        >
          <main style={{ padding: 24 }}>
            <ReturnToNext />
            <Routes>
              <Route path="/" element={<RecipesPage />} />
              <Route path="/recipes" element={<RecipesPage />} />
              <Route path="/meal-plan" element={<MealPlanPage />} />
              <Route path="/ingredients" element={<IngredientsPage />} />
              <Route path="/shopping-list" element={<ShoppingListPage />} />
              <Route path="/import-export" element={<ImportExportPage />} />
              <Route path="/shared-with-me" element={<SharedWithMePage />} />
              <Route path="/shared/:token" element={<SharedRecipePage />} />
            </Routes>
          </main>
        </div>
      </div>
    </div>
  )
}

function Gate() {
  const { user, loading } = useAuth()

  if (loading) {
    return (
      <div
        className="flex items-center justify-center"
        style={{ minHeight: '100vh', color: 'var(--text-muted)' }}
      >
        Loading…
      </div>
    )
  }

  if (!user) {
    // The verify/reset flows are reached from emailed links while logged out, so
    // they must be routable before authentication; everything else falls to login.
    return (
      <Routes>
        <Route path="/verify-email" element={<VerifyEmailPage />} />
        <Route path="/forgot-password" element={<ForgotPasswordPage />} />
        <Route path="/reset-password" element={<ResetPasswordPage />} />
        <Route path="*" element={<LoginPage />} />
      </Routes>
    )
  }

  // UN-11 / D-7. A handle the user has never confirmed is system-assigned from
  // the email local part (anna.rossi@… → anna_rossi), so it partially discloses
  // the address. Nothing may render until it is confirmed. This is deliberately
  // *not* a <Route>: no <Routes> element exists on this branch, so there is no
  // path — and no in-app navigation — that can reach the shell around it.
  // It fails closed: anything other than an explicit `true` blocks.
  if (user.username_confirmed !== true) {
    return <ChooseHandlePage />
  }

  return <Shell />
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Gate />
      </BrowserRouter>
    </AuthProvider>
  )
}
