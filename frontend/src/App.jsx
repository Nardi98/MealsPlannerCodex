import React, { useState } from 'react';
import {
  BrowserRouter as Router,
  Routes,
  Route,
  useLocation,
  useNavigate,
} from 'react-router-dom';
import {
  SwatchIcon,
  CalendarDaysIcon,
  BookOpenIcon,
  Squares2X2Icon,
  ShoppingCartIcon,
  ArrowPathIcon,
} from '@heroicons/react/24/outline';

import Recipes from './pages/Recipes';
import Ingredients from './pages/Ingredients';
import NewPlan from './pages/NewPlan';
import PlanView from './pages/PlanView';
import ImportExport from './pages/ImportExport';
import GroceryList from './pages/GroceryList';
import NavItem from './components/NavItem';
import Input from './components/Input';
import { useCssVars } from './tokens';

export const AppContext = React.createContext();

function Shell() {
  const location = useLocation();
  const navigate = useNavigate();

  const navItems = [
    { label: 'Week planner', to: '/plan-view', Icon: CalendarDaysIcon, disabled: true },
    { label: 'Recipes', to: '/', Icon: BookOpenIcon, disabled: false },
    { label: 'Ingredients', to: '/ingredients', Icon: Squares2X2Icon, disabled: true },
    { label: 'Shopping list', to: '/grocery-list', Icon: ShoppingCartIcon, disabled: true },
    { label: 'Import/Export', to: '/import-export', Icon: ArrowPathIcon, disabled: true },
  ];

  return (
    <>
      <header className="border-b" style={{ borderColor: 'var(--border)' }}>
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3">
          <div className="flex items-center gap-2">
            <SwatchIcon className="h-6 w-6 text-[color:var(--c-a3)]" />
            <span className="font-semibold">Meal Planner</span>
          </div>
          <div className="flex items-center gap-3">
            <Input placeholder="Search recipes..." className="w-64" />
            <div className="h-8 w-8 rounded-full bg-[color:var(--border)]" />
          </div>
        </div>
      </header>

      <main className="mx-auto grid max-w-7xl grid-cols-1 gap-4 px-4 py-6 md:grid-cols-[16rem_1fr]">
        <aside className="space-y-2">
          <div
            className="rounded-2xl border bg-white p-4 shadow-sm"
            style={{ borderColor: 'var(--border)' }}
          >
            <div className="grid grid-cols-1 gap-1">
              {navItems.map((item) => (
                <NavItem
                  key={item.label}
                  active={location.pathname === item.to}
                  Icon={item.Icon}
                  label={item.label}
                  disabled={item.disabled}
                  onClick={() => !item.disabled && navigate(item.to)}
                />
              ))}
            </div>
          </div>
        </aside>
        <section className="space-y-4">
          <Routes>
            <Route path="/" element={<Recipes />} />
            <Route path="/ingredients" element={<Ingredients />} />
            <Route path="/new-plan" element={<NewPlan />} />
            <Route path="/plan-view" element={<PlanView />} />
            <Route path="/grocery-list" element={<GroceryList />} />
            <Route path="/import-export" element={<ImportExport />} />
          </Routes>
        </section>
      </main>
    </>
  );
}

export default function App() {
  const [recipes, setRecipes] = useState([]);
  const [plan, setPlan] = useState({}); // { [date]: Array<{ main: string, sides: string[] }> }
  const value = { recipes, setRecipes, plan, setPlan };
  const cssVars = useCssVars();

  return (
    <div
      className="min-h-screen"
      style={{ ...cssVars, background: 'var(--c-white)', color: 'var(--text-strong)' }}
    >
      <AppContext.Provider value={value}>
        <Router>
          <Shell />
        </Router>
      </AppContext.Provider>
    </div>
  );
}

