import React, { useState } from 'react'
import {
  BrowserRouter as Router,
  Routes,
  Route,
  useLocation,
  useNavigate,
} from 'react-router-dom'
import NavItem from './ui/NavItem'
import Recipes from './pages/Recipes'
import Ingredients from './pages/Ingredients'
import NewPlan from './pages/NewPlan'
import PlanView from './pages/PlanView'
import ImportExport from './pages/ImportExport'
import GroceryList from './pages/GroceryList'
import UiPreview from './pages/UiPreview'

export const AppContext = React.createContext()

function AppNav() {
  const location = useLocation()
  const navigate = useNavigate()
  const items = [
    { to: '/', label: 'Recipes' },
    { to: '/ingredients', label: 'Ingredients' },
    { to: '/new-plan', label: 'New Plan' },
    { to: '/plan-view', label: 'Plan View' },
    { to: '/grocery-list', label: 'Grocery List' },
    { to: '/import-export', label: 'Import / Export' },
    { to: '/ui-preview', label: 'UI Preview' },
  ]
  return (
    <header className="border-b" style={{ borderColor: 'var(--border)' }}>
      <nav className="mx-auto flex max-w-7xl gap-2 px-4 py-3">
        {items.map(({ to, label }) => (
          <NavItem
            key={to}
            label={label}
            active={location.pathname === to}
            onClick={() => navigate(to)}
          />
        ))}
      </nav>
    </header>
  )
}

export default function App() {
  const [recipes, setRecipes] = useState([])
  const [plan, setPlan] = useState({}) // { [date]: Array<{ main: string, sides: string[] }> }
  const value = { recipes, setRecipes, plan, setPlan }

  return (
    <AppContext.Provider value={value}>
      <Router>
        <AppNav />
        <Routes>
          <Route path="/" element={<Recipes />} />
          <Route path="/ingredients" element={<Ingredients />} />
          <Route path="/new-plan" element={<NewPlan />} />
          <Route path="/plan-view" element={<PlanView />} />
          <Route path="/grocery-list" element={<GroceryList />} />
          <Route path="/import-export" element={<ImportExport />} />
          <Route path="/ui-preview" element={<UiPreview />} />
        </Routes>
      </Router>
    </AppContext.Provider>
  )
}
