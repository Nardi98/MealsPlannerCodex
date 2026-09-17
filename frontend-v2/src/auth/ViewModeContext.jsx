import React from 'react'
import { useAuth } from './AuthContext'

/**
 * Which hat the account is wearing: its own, or the library administrator's.
 *
 * An admin account is one account with two jobs -- keeping a recipe book and
 * curating the shared library -- and mixing them on one screen is what this
 * exists to undo. The mode is deliberately *not* persisted: it lives in React
 * state, so every reload and every sign-in starts as a plain user, and admin is
 * always a thing you chose on purpose this session.
 *
 * It is not a permission. The server decides what an admin may do (every
 * `/admin/catalog/*` route is behind `require_admin`); this only decides what
 * is shown, exactly like `is_admin` did before it.
 */
// The default is what a component outside the provider sees: no admin
// anywhere, so `Sidebar` and friends stay renderable -- and unit-testable --
// on their own.
const ViewModeContext = React.createContext({
  mode: 'user',
  isAdminMode: false,
  canAdmin: false,
  setMode: () => {},
})

export function ViewModeProvider({ children }) {
  const { user } = useAuth()
  const canAdmin = user?.is_admin === true
  // What the account has *asked* for. Whether it gets it is decided below, on
  // every render, so an account that loses the flag mid-session drops out of
  // admin mode without anything having to notice and reset this.
  const [wanted, setMode] = React.useState('user')

  // The one place the mode is decided, and it fails closed: `mode` is derived
  // from this too, so there is no second spelling for a reader to reconcile.
  const isAdminMode = canAdmin && wanted === 'admin'

  const value = React.useMemo(
    () => ({ mode: isAdminMode ? 'admin' : 'user', isAdminMode, canAdmin, setMode }),
    [isAdminMode, canAdmin],
  )
  return <ViewModeContext.Provider value={value}>{children}</ViewModeContext.Provider>
}

// Co-locating the hook with its provider is the standard React Context pattern.
// eslint-disable-next-line react-refresh/only-export-components
export function useViewMode() {
  return React.useContext(ViewModeContext)
}
