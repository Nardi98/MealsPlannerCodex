import React, { useState } from 'react';
import { SwatchIcon, CalendarDaysIcon, BookmarkIcon, ShoppingCartIcon, MagnifyingGlassIcon } from '@heroicons/react/24/outline';
import { useCssVars } from './tokens';

function NavItem({ active, Icon, label, onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`w-full text-left flex items-center gap-3 rounded-xl px-3 py-2 hover:opacity-95 ${active ? 'text-white' : 'text-[color:var(--text-strong)]'}`}
      style={{ backgroundColor: active ? 'var(--c-a1)' : 'transparent' }}
    >
      <Icon className="h-5 w-5" />
      <span className="text-sm font-medium">{label}</span>
    </button>
  );
}

export default function App() {
  const [active, setActive] = useState('recipes');
  const cssVars = useCssVars();

  return (
    <div className="min-h-screen" style={{ ...cssVars, background: 'var(--c-white)', color: 'var(--text-strong)' }}>
      <header className="border-b" style={{ borderColor: 'var(--border)' }}>
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3">
          <div className="flex items-center gap-2">
            <SwatchIcon className="h-6 w-6 text-[color:var(--c-a3)]" />
            <span className="font-semibold">Meal Planner</span>
            <span className="text-xs text-[color:var(--text-subtle)] ml-2">Demo UI — Updated Style</span>
          </div>
          <div className="hidden md:flex items-center gap-2">
            <input
              className="rounded-xl border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[color:var(--c-a2)] w-64"
              placeholder="Search…"
              style={{ borderColor: 'var(--border)' }}
            />
            <button
              className="inline-flex items-center gap-2 rounded-2xl border px-3 py-2 text-sm hover:opacity-95"
              style={{ color: 'var(--text-strong)', borderColor: 'var(--border)' }}
              type="button"
            >
              <MagnifyingGlassIcon className="h-4 w-4" />
              <span>Search</span>
            </button>
            <div className="h-8 w-8 rounded-full bg-[color:var(--c-a3)]" />
          </div>
        </div>
      </header>

      <main className="mx-auto grid max-w-7xl grid-cols-1 gap-4 px-4 py-6 md:grid-cols-[16rem_1fr]">
        <aside className="space-y-2">
          <div className="rounded-2xl border bg-white p-4 shadow-sm" style={{ borderColor: 'var(--border)' }}>
            <div className="grid grid-cols-1 gap-1">
              <NavItem active={active === 'planner'} onClick={() => setActive('planner')} Icon={CalendarDaysIcon} label="Week planner" />
              <NavItem active={active === 'recipes'} onClick={() => setActive('recipes')} Icon={BookmarkIcon} label="Recipes" />
              <NavItem active={active === 'list'} onClick={() => setActive('list')} Icon={ShoppingCartIcon} label="Shopping list" />
            </div>
          </div>
        </aside>
        <section className="space-y-4">
          <div className="rounded-2xl border bg-white p-4 shadow-sm" style={{ borderColor: 'var(--border)' }}>
            <p className="text-sm text-[color:var(--text-muted)]">Active page: {active}</p>
          </div>
        </section>
      </main>
    </div>
  );
}
