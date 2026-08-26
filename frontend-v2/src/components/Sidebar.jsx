import React from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import {
  CalendarDaysIcon,
  BookmarkIcon,
  ShoppingCartIcon,
  BeakerIcon,
  ArrowUpTrayIcon,
  InboxArrowDownIcon,
} from '@heroicons/react/24/outline'

const NAV = [
  { label: 'Recipes', path: '/recipes', Icon: BookmarkIcon, color: 'var(--cat-berry)', match: (p) => p === '/' || p === '/recipes' },
  { label: 'Meal Plan', path: '/meal-plan', Icon: CalendarDaysIcon, color: 'var(--c-a2)', match: (p) => p === '/meal-plan' },
  { label: 'Shared with me', path: '/shared-with-me', Icon: InboxArrowDownIcon, color: 'var(--cat-sky)', match: (p) => p === '/shared-with-me' },
  { label: 'Ingredients', path: '/ingredients', Icon: BeakerIcon, color: 'var(--cat-olive)', match: (p) => p === '/ingredients' },
  { label: 'Shopping List', path: '/shopping-list', Icon: ShoppingCartIcon, color: 'var(--cat-teal)', match: (p) => p === '/shopping-list' },
  { label: 'Import/Export', path: '/import-export', Icon: ArrowUpTrayIcon, color: 'var(--cat-plum)', match: (p) => p === '/import-export' },
]

// The green nav panel. Rendered as a sticky column on desktop and inside
// `NavDrawer` on mobile, which is why `onNavigate` exists: the drawer needs to
// close itself once a destination has been picked.
export default function Sidebar({ onNavigate }) {
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
            onClick={() => {
              navigate(path)
              if (onNavigate) onNavigate()
            }}
            className="flex items-center gap-3 text-left"
            style={{
              // 44px tall: the minimum comfortable tap target on a phone.
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
