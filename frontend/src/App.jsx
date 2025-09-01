import React, { useState } from 'react'
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import Recipes from './pages/Recipes'
import Ingredients from './pages/Ingredients'
import NewPlan from './pages/NewPlan'
import PlanView from './pages/PlanView'
import ImportExport from './pages/ImportExport'
import GroceryList from './pages/GroceryList'
import AppShell from './AppShell'

export const AppContext = React.createContext()

export default function App() {
  const [recipes, setRecipes] = useState([])
  const [plan, setPlan] = useState({}) // { [date]: Array<{ main: string, sides: string[] }> }
  const value = { recipes, setRecipes, plan, setPlan }

  return (
    <AppContext.Provider value={value}>
      <Router>
        <AppShell>
          <Routes>
            <Route path="/" element={<Recipes />} />
            <Route path="/ingredients" element={<Ingredients />} />
            <Route path="/new-plan" element={<NewPlan />} />
            <Route path="/plan-view" element={<PlanView />} />
            <Route path="/grocery-list" element={<GroceryList />} />
            <Route path="/import-export" element={<ImportExport />} />
          </Routes>
        </AppShell>
      </Router>
    </AppContext.Provider>
  )
}
