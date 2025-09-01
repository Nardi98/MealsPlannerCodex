import React from 'react';
import { SwatchIcon, CalendarDaysIcon, BookmarkIcon, ShoppingCartIcon, MagnifyingGlassIcon, PlusIcon } from '@heroicons/react/24/outline';
import { useNavigate, useLocation } from 'react-router-dom';
import { NavItem } from './components/NavItem';
import { Button } from './components/Button';
import { useCssVars } from './tokens';

export default function AppShell({ children }) {
  const navigate = useNavigate();
  const location = useLocation();
  const vars = useCssVars();

  const items = [
    { label: 'Week planner', to: '/plan-view', Icon: CalendarDaysIcon },
    { label: 'Recipes', to: '/', Icon: BookmarkIcon },
    { label: 'Shopping list', to: '/grocery-list', Icon: ShoppingCartIcon },
  ];

  return (
    <div className="min-h-screen flex flex-col" style={{ ...vars, background: 'var(--c-white)', color: 'var(--text-strong)' }}>
      <header className="border-b" style={{ borderColor: 'var(--border)' }}>
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-2">
          <div className="flex items-center gap-2">
            <SwatchIcon className="h-5 w-5 text-[color:var(--c-a3)]" />
            <span className="font-semibold">Meal Planner</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="relative">
              <MagnifyingGlassIcon className="pointer-events-none absolute left-3 top-1/2 h-5 w-5 -translate-y-1/2 text-[color:var(--text-subtle)]" />
              <input
                className="w-64 rounded-xl border pl-9 pr-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[color:var(--c-a2)]"
                placeholder="Search recipes..."
                style={{ borderColor: 'var(--border)' }}
              />
            </div>
            <Button variant="ghost" className="hidden md:inline-flex" Icon={PlusIcon}>New recipe</Button>
            <div className="h-8 w-8 rounded-full bg-[color:var(--border)]" />
          </div>
        </div>
      </header>
      <div className="mx-auto flex w-full max-w-7xl flex-1">
        <aside className="w-48 border-r p-3 flex flex-col gap-1" style={{ borderColor: 'var(--border)' }}>
          {items.map((it) => (
            <NavItem
              key={it.to}
              active={location.pathname === it.to}
              Icon={it.Icon}
              label={it.label}
              onClick={() => navigate(it.to)}
            />
          ))}
        </aside>
        <main className="flex-1 p-4">{children}</main>
      </div>
    </div>
  );
}
