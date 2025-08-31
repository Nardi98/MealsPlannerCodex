import React, { useState } from 'react'
import {
  BrowserRouter as Router,
  Routes,
  Route,
  useLocation,
  useNavigate,
} from 'react-router-dom'
import {
  SwatchIcon,
  CalendarDaysIcon,
  BookmarkIcon,
  ShoppingCartIcon,
  MagnifyingGlassIcon,
} from '@heroicons/react/24/outline'
import { NavItem } from './components/NavItem'
import Recipes from './pages/Recipes'
import WeekPlannerPage from './pages/WeekPlannerPage'
import ShoppingListPage from './pages/ShoppingListPage'
import { useCssVars } from './tokens'

export const AppContext = React.createContext()

function Shell() {
  const [recipes, setRecipes] = useState([])
  const [plan, setPlan] = useState({})
  const value = { recipes, setRecipes, plan, setPlan }
  const cssVars = useCssVars()
  const location = useLocation()
  const navigate = useNavigate()

  const active = location.pathname.startsWith('/week-planner')
    ? 'week'
    : location.pathname.startsWith('/shopping-list')
    ? 'shopping'
    : 'recipes'

  return (
    <AppContext.Provider value={value}>
      <div
        className="min-h-screen flex flex-col"
        style={{
          ...cssVars,
          background: 'var(--c-white)',
          color: 'var(--text-strong)',
        }}
      >
        <header className="border-b" style={{ borderColor: 'var(--border)' }}>
          <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3">
            <div className="flex items-center gap-2">
              <SwatchIcon className="h-6 w-6 text-[color:var(--c-a3)]" />
              <span className="font-semibold">Meal Planner</span>
            </div>
            <div className="flex items-center gap-4">
              <div className="hidden md:flex items-center gap-2">
                <input
                  className="rounded-xl border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[color:var(--c-a2)] w-64"
                  placeholder="Search…"
                  style={{ borderColor: 'var(--border)' }}
                />
                <button
                  className="inline-flex items-center rounded-2xl border px-3 py-2 text-sm hover:opacity-95"
                  style={{ borderColor: 'var(--border)', color: 'var(--text-strong)' }}
                >
                  <MagnifyingGlassIcon className="h-4 w-4" />
                </button>
              </div>
              <div className="h-8 w-8 rounded-full bg-[color:var(--border)]" />
            </div>
          </div>
        </header>
        <div className="flex flex-1">
          <aside className="w-56 border-r p-4" style={{ borderColor: 'var(--border)' }}>
            <nav className="flex flex-col gap-1">
              <NavItem
                variant={active === 'recipes' ? 'active' : 'default'}
                Icon={BookmarkIcon}
                label="Recipes"
                onClick={() => navigate('/')}
              />
              <NavItem
                variant={active === 'week' ? 'active' : 'default'}
                Icon={CalendarDaysIcon}
                label="Week Planner"
                onClick={() => navigate('/week-planner')}
              />
              <NavItem
                variant={active === 'shopping' ? 'active' : 'default'}
                Icon={ShoppingCartIcon}
                label="Shopping List"
                onClick={() => navigate('/shopping-list')}
              />
            </nav>
          </aside>
          <main className="flex-1 p-4">
            <Routes>
              <Route path="/" element={<Recipes />} />
              <Route path="/week-planner" element={<WeekPlannerPage />} />
              <Route path="/shopping-list" element={<ShoppingListPage />} />
            </Routes>
          </main>
        </div>
      </div>
    </AppContext.Provider>
  )
}

export default function AppShell() {
  return (
    <Router>
      <Shell />
    </Router>
  )
}
