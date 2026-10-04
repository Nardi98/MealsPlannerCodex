import React from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import {
  CalendarDaysIcon,
  BookmarkIcon,
  ShoppingCartIcon,
  BeakerIcon,
  ArrowUpTrayIcon,
  InboxArrowDownIcon,
  TagIcon,
  CloudArrowUpIcon,
  EnvelopeIcon, // ALPHA-GATE
  ChatBubbleLeftEllipsisIcon,
  SparklesIcon,
} from '@heroicons/react/24/outline'
import { useViewMode } from '../auth/ViewModeContext'

// `modes` is the entry's own answer to "who is this for", so the app's
// information architecture lives here rather than as a path comparison in the
// render below: a new admin surface is one more `'admin'`, and renaming a path
// cannot silently empty the menu.
const BOTH = ['user', 'admin']
const USER_ONLY = ['user']
const ADMIN_ONLY = ['admin']

const NAV = [
  { label: 'Recipes', path: '/recipes', Icon: BookmarkIcon, color: 'var(--cat-berry)', modes: USER_ONLY, match: (p) => p === '/' || p === '/recipes' },
  // Terracotta: the last distinct category hue not already on a nav icon (the
  // other unused tokens -- sage, clay, forest -- alias core chrome colours).
  { label: 'Discover', path: '/discover', Icon: SparklesIcon, color: 'var(--cat-terracotta)', modes: BOTH, match: (p) => p === '/discover' },
  // Admin-only catalog surfaces, kept next to Discover because they are the
  // same library seen from the other side: its vocabulary and its intake. The
  // import review page has no entry -- it is reached per recipe from Import.
  { label: 'Ingredients & Tags', path: '/discover/vocabulary', Icon: TagIcon, color: 'var(--cat-sky)', modes: ADMIN_ONLY, match: (p) => p === '/discover/vocabulary' },
  { label: 'Import', path: '/discover/import', Icon: CloudArrowUpIcon, color: 'var(--cat-plum)', modes: ADMIN_ONLY, match: (p) => p.startsWith('/discover/import') },
  // ALPHA-GATE: clay (--c-a3) is the one remaining category token that is not
  // the panel's own green -- forest and sage would vanish into it.
  { label: 'Alpha', path: '/discover/alpha', Icon: EnvelopeIcon, color: 'var(--cat-clay)', modes: ADMIN_ONLY, match: (p) => p === '/discover/alpha' },
  // Last, after the catalog surfaces: it is about the app as a whole, not the
  // library. Berry is also Recipes' colour, but Recipes is user-only, so the two
  // are never on screen together -- and every other distinct hue is taken.
  { label: 'Feedback', path: '/discover/feedback', Icon: ChatBubbleLeftEllipsisIcon, color: 'var(--cat-berry)', modes: ADMIN_ONLY, match: (p) => p === '/discover/feedback' },
  { label: 'Meal Plan', path: '/meal-plan', Icon: CalendarDaysIcon, color: 'var(--c-a2)', modes: USER_ONLY, match: (p) => p === '/meal-plan' },
  { label: 'Shared with me', path: '/shared-with-me', Icon: InboxArrowDownIcon, color: 'var(--cat-sky)', modes: USER_ONLY, match: (p) => p === '/shared-with-me' },
  { label: 'Ingredients', path: '/ingredients', Icon: BeakerIcon, color: 'var(--cat-olive)', modes: USER_ONLY, match: (p) => p === '/ingredients' },
  { label: 'Shopping List', path: '/shopping-list', Icon: ShoppingCartIcon, color: 'var(--cat-teal)', modes: USER_ONLY, match: (p) => p === '/shopping-list' },
  { label: 'Import/Export', path: '/import-export', Icon: ArrowUpTrayIcon, color: 'var(--cat-plum)', modes: USER_ONLY, match: (p) => p === '/import-export' },
]

// Both menus are fixed, so they are built once rather than filtered per render.
const NAV_FOR = {
  user: NAV.filter((item) => item.modes.includes('user')),
  admin: NAV.filter((item) => item.modes.includes('admin')),
}

// The green nav panel. Rendered as a sticky column on desktop and inside
// `NavDrawer` on mobile, which is why `onNavigate` exists: the drawer needs to
// close itself once a destination has been picked.
//
// In admin mode it shows only the entries marked for that mode, so an admin
// gets the one surface they have -- the same entry, icon and colour it is in
// user mode. The other pages remain routable: this hides them, it does not gate
// them, and nothing here is a permission.
//
// `badges` maps an entry's path to a count shown beside it (the unread feedback
// count). The caller fetches it once for both copies of this panel -- desktop
// and drawer -- so a phone does not ask twice.
export default function Sidebar({ onNavigate, badges }) {
  const navigate = useNavigate()
  const location = useLocation()
  const items = NAV_FOR[useViewMode().mode]

  return (
    <div
      className="surface-dark flex flex-col gap-1"
      style={{
        borderRadius: 'var(--radius-lg)',
        boxShadow: 'var(--shadow-md)',
        padding: 12,
        width: 'var(--sidebar-width)',
        height: '100%',
        boxSizing: 'border-box',
      }}
    >
      {items.map((item) => {
        const { label, path, color, match } = item
        const NavIcon = item.Icon
        const active = match(location.pathname)
        const count = badges?.[path]
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
            {count > 0 && <CountPill count={count} />}
          </button>
        )
      })}
    </div>
  )
}

// Not the `Badge` primitive: that one is a 16% tint tuned for white surfaces and
// would all but vanish on the forest panel. Mustard with dark text is the
// guide's own accent pairing (`--accent-primary` / `--text-on-accent`), so it
// reads as chrome rather than as one more category colour.
function CountPill({ count }) {
  return (
    <span
      aria-label={`${count} unread`}
      className="ml-auto inline-flex items-center justify-center rounded-full"
      style={{
        minWidth: 20,
        padding: '1px 7px',
        background: 'var(--accent-primary)',
        color: 'var(--text-on-accent)',
        fontFamily: 'var(--font-display)',
        fontWeight: 'var(--weight-semibold)',
        fontSize: 'var(--text-xs)',
      }}
    >
      {count}
    </span>
  )
}
