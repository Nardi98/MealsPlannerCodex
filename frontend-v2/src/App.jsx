import { BrowserRouter, Routes, Route, useLocation, useNavigate } from 'react-router-dom'
import {
  SwatchIcon,
  CalendarDaysIcon,
  BookmarkIcon,
  ShoppingCartIcon,
  MagnifyingGlassIcon,
  BeakerIcon,
  ArrowUpTrayIcon,
} from '@heroicons/react/24/outline'
import { NavItem, Input, Button } from './components'
import RecipesPage from './pages/RecipesPage'
import MealPlanPage from './pages/MealPlanPage'
import IngredientsPage from './pages/IngredientsPage'
import ShoppingListPage from './pages/ShoppingListPage'
import ImportExportPage from './pages/ImportExportPage'

function Shell() {
  const navigate = useNavigate()
  const location = useLocation()

  return (
    <div className="min-h-screen" style={{ background: 'var(--c-white)', color: 'var(--text-strong)' }}>
      <header className="border-b" style={{ borderColor: 'var(--border)' }}>
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3">
          <div className="flex items-center gap-2">
            <SwatchIcon className="h-6 w-6 text-[color:var(--c-a3)]" />
            <span className="font-semibold">Meal Planner</span>
          </div>
          <div className="hidden md:flex items-center gap-2">
            <Input placeholder="Search…" className="w-64" />
            <Button variant="ghost" Icon={MagnifyingGlassIcon}>Search</Button>
            <div className="h-8 w-8 rounded-full bg-[color:var(--text-muted)]"></div>
          </div>
        </div>
      </header>

      <main className="mx-auto grid max-w-7xl grid-cols-1 gap-4 px-4 py-6 md:grid-cols-[16rem_1fr]">
        <aside className="space-y-2">
          <div className="rounded-2xl border bg-white p-4 shadow-sm" style={{ borderColor: 'var(--border)' }}>
            <nav className="grid grid-cols-1 gap-1">
              <NavItem
                active={location.pathname === '/' || location.pathname === '/recipes'}
                onClick={() => navigate('/recipes')}
                Icon={BookmarkIcon}
                label="Recipes"
              />
              <NavItem
                Icon={CalendarDaysIcon}
                label="Meal Plan"
                className="text-[color:var(--text-subtle)] cursor-not-allowed"
                aria-disabled="true"
              />
              <NavItem
                active={location.pathname === '/ingredients'}
                onClick={() => navigate('/ingredients')}
                Icon={BeakerIcon}
                label="Ingredients"
              />
              <NavItem
                Icon={ShoppingCartIcon}
                label="Shopping List"
                className="text-[color:var(--text-subtle)] cursor-not-allowed"
                aria-disabled="true"
              />
              <NavItem
                Icon={ArrowUpTrayIcon}
                label="Import/Export"
                className="text-[color:var(--text-subtle)] cursor-not-allowed"
                aria-disabled="true"
              />
            </nav>
          </div>
        </aside>
        <section className="space-y-4">
          <Routes>
            <Route path="/" element={<RecipesPage />} />
            <Route path="/recipes" element={<RecipesPage />} />
            <Route path="/meal-plan" element={<MealPlanPage />} />
            <Route path="/ingredients" element={<IngredientsPage />} />
            <Route path="/shopping-list" element={<ShoppingListPage />} />
            <Route path="/import-export" element={<ImportExportPage />} />
          </Routes>
        </section>
      </main>
    </div>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <Shell />
    </BrowserRouter>
  )
}

