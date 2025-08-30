import React, { useState } from 'react'
import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom'
import Recipes from './pages/Recipes'
import Ingredients from './pages/Ingredients'
import NewPlan from './pages/NewPlan'
import PlanView from './pages/PlanView'
import ImportExport from './pages/ImportExport'
import GroceryList from './pages/GroceryList'

export const AppContext = React.createContext()

export default function App() {
  const [recipes, setRecipes] = useState([])
  const [plan, setPlan] = useState({}) // { [date]: Array<{ main: string, sides: string[] }> }
  const value = { recipes, setRecipes, plan, setPlan }

  return (
    <AppContext.Provider value={value}>
      <Router>
        <nav>
          <Link to="/">Recipes</Link>
          <Link to="/ingredients">Ingredients</Link>
          <Link to="/new-plan">New Plan</Link>
          <Link to="/plan-view">Plan View</Link>
          <Link to="/grocery-list">Grocery List</Link>
          <Link to="/import-export">Import / Export</Link>
        </nav>
        <Routes>
          <Route path="/" element={<Recipes />} />
          <Route path="/ingredients" element={<Ingredients />} />
          <Route path="/new-plan" element={<NewPlan />} />
          <Route path="/plan-view" element={<PlanView />} />
          <Route path="/grocery-list" element={<GroceryList />} />
          <Route path="/import-export" element={<ImportExport />} />
        </Routes>
      </Router>
    </AppContext.Provider>
  )
}
