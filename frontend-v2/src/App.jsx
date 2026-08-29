import React from 'react'
import { BrowserRouter, Navigate, Routes, Route, useLocation } from 'react-router-dom'
import { Bars3Icon } from '@heroicons/react/24/outline'
import { Input, ProfileMenu } from './components'
import Sidebar from './components/Sidebar'
import NavDrawer from './components/NavDrawer'
import { useIsMobile } from './hooks/useIsMobile'
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
import { TutorialProvider, ReplayTutorialButton } from './tutorial/TutorialProvider'

// Where a freshly-authenticated user goes when nothing better is known.
const DEFAULT_LANDING = '/recipes'

// SH-23. Redirects to a `?next=` destination on the first authenticated render.
//
// Declarative rather than an effect. An effect that called `navigate` raced the
// catch-all `<Route path="*">` below: both fire after the same commit, and if
// the catch-all won it replaced `/login?next=…` with the default page and threw
// the token away — the exact bug this component exists to fix, reintroduced by
// its own fix. Returning a `<Navigate>` resolves during render, so the shell's
// routes never see a path this was going to redirect away from.
//
// It wraps the shell from *inside* the authenticated branch on purpose. The
// gate above it (`username_confirmed`) is not a page a redirect may skip, so an
// unconfirmed account never reaches this component and a `next` cannot be used
// to route around handle selection (UN-11).
//
// `replace` so the consumed `/login?next=…` does not sit in history: the back
// button should return the user to wherever they came from, not to a sign-in
// URL that immediately redirects them forward again.
//
// A rejected `next` is deliberately indistinguishable from an absent one — both
// simply fall through to `children`, and from there to the catch-all route.
// There is nothing useful to tell the user, and naming the refusal would only
// confirm to an attacker which shapes are filtered.
function ReturnToNext({ children }) {
  const destination = nextFromSearch(useLocation().search)
  if (destination) return <Navigate to={destination} replace />
  return children
}


function Shell() {
  const rowRef = React.useRef(null)
  const wrapRef = React.useRef(null)
  const isMobile = useIsMobile()
  const [menuOpen, setMenuOpen] = React.useState(false)
  const closeMenu = React.useCallback(() => setMenuOpen(false), [])

  // The burger is only hidden on desktop, not unmounted, so a `menuOpen` left
  // over from a phone-width session would have it reporting itself as expanded.
  React.useEffect(() => {
    if (!isMobile) setMenuOpen(false)
  }, [isMobile])

  React.useEffect(() => {
    if (isMobile) return undefined
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
  }, [isMobile])

  return (
    <div className="min-h-screen box-border p-3 md:p-5">
      <header
        className="flex items-center justify-between gap-2 pb-4 pl-2 pr-2 pt-1 md:pb-[18px] md:pl-6"
      >
        <div className="flex items-center gap-2 min-w-0">
          <button
            type="button"
            aria-label="Open menu"
            aria-expanded={menuOpen}
            onClick={() => setMenuOpen((v) => !v)}
            className="md:hidden flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border-0 bg-transparent cursor-pointer"
          >
            <Bars3Icon className="h-6 w-6" style={{ color: 'var(--c-pos)' }} />
          </button>
          <img
            src="/assets/Logo_mealplanner.png"
            alt="Meal Planner logo"
            className="h-10 md:h-[52px]"
            style={{ opacity: 0.9 }}
          />
        </div>
        {/* Only the search moves into the drawer on mobile. Help and the account
            menu stay put: a tutorial nobody can find is a tutorial nobody runs,
            and logging out must never be more than one tap away. */}
        <div className="flex items-center gap-3">
          <Input placeholder="Search…" style={{ width: 220 }} className="hidden md:block" />
          <ReplayTutorialButton />
          <ProfileMenu />
        </div>
      </header>

      <NavDrawer
        open={isMobile && menuOpen}
        onClose={closeMenu}
        header={<Input placeholder="Search…" className="w-full" />}
      />

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
          className="hidden md:block flex-shrink-0 sticky top-5 overflow-hidden"
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
          <main className="p-4 md:p-6">
            <Routes>
              <Route path="/" element={<RecipesPage />} />
              <Route path="/recipes" element={<RecipesPage />} />
              <Route path="/meal-plan" element={<MealPlanPage />} />
              <Route path="/ingredients" element={<IngredientsPage />} />
              <Route path="/shopping-list" element={<ShoppingListPage />} />
              <Route path="/import-export" element={<ImportExportPage />} />
              <Route path="/shared-with-me" element={<SharedWithMePage />} />
              <Route path="/shared/:token" element={<SharedRecipePage />} />
              {/*
                Anything the shell has no route for — `/login` after signing in,
                `/verify-email`, a stale bookmark, a typo. Declarative and
                general: the alternative was a hand-maintained list of the
                logged-out paths in `Gate`, 200 lines away, which silently
                rendered a blank <main> the first time somebody added a route
                to one list and not the other.
              */}
              <Route path="*" element={<Navigate to={DEFAULT_LANDING} replace />} />
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

  return (
    <ReturnToNext>
      {/* Wraps the shell, not the routes: the replay button lives in the header
          and the tours live in the pages, so both need the same provider. */}
      <TutorialProvider>
        <Shell />
      </TutorialProvider>
    </ReturnToNext>
  )
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
