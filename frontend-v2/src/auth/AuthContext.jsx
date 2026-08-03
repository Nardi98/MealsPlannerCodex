import React from 'react'
import { authApi } from '../api/authApi'
import { setAuthToken, setUnauthorizedHandler } from '../api/client'

const AuthContext = React.createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = React.useState(null)
  // The access token never survives a reload, so we always begin by trying to
  // restore the session from the HttpOnly refresh cookie.
  const [loading, setLoading] = React.useState(true)

  const logout = React.useCallback(async () => {
    try {
      await authApi.logout()
    } catch {
      // Best-effort: even if the server call fails, drop the client session.
    }
    setAuthToken(null)
    setUser(null)
  }, [])

  // A failed refresh means our session is irrecoverable — drop it everywhere.
  React.useEffect(() => {
    setUnauthorizedHandler(() => {
      setAuthToken(null)
      setUser(null)
    })
    return () => setUnauthorizedHandler(null)
  }, [])

  // Bootstrap on load: swap the refresh cookie for an access token, then load
  // the account. A missing/expired cookie just lands us on the login screen.
  React.useEffect(() => {
    let active = true
    authApi
      .refresh()
      .then(async ({ access_token }) => {
        setAuthToken(access_token)
        const u = await authApi.me()
        if (active) setUser(u)
      })
      .catch(() => active && setAuthToken(null))
      .finally(() => active && setLoading(false))
    return () => {
      active = false
    }
  }, [])

  // Every sign-in path ends the same way: keep the issued token, then load the
  // account it belongs to.
  const startSession = React.useCallback(async ({ access_token }) => {
    setAuthToken(access_token)
    const u = await authApi.me()
    setUser(u)
    return u
  }, [])

  const login = React.useCallback(
    async (credentials) => startSession(await authApi.login(credentials)),
    [startSession],
  )

  const loginWithGoogle = React.useCallback(
    async (credential) => startSession(await authApi.google({ credential })),
    [startSession],
  )

  // Registration no longer logs in — the account is unverified until the user
  // follows the emailed link. Returns the created user for the "check email" UI.
  const register = React.useCallback(
    async (payload) => authApi.register(payload),
    [],
  )

  const value = React.useMemo(
    () => ({ user, loading, login, register, logout, loginWithGoogle }),
    [user, loading, login, register, logout, loginWithGoogle],
  )
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

// Co-locating the hook with its provider is the standard React Context pattern.
// eslint-disable-next-line react-refresh/only-export-components
export function useAuth() {
  const ctx = React.useContext(AuthContext)
  if (ctx === null) throw new Error('useAuth must be used within an AuthProvider')
  return ctx
}
