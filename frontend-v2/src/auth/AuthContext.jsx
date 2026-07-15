import React from 'react'
import { authApi } from '../api/authApi'
import { getToken, setAuthToken, setUnauthorizedHandler } from '../api/client'

const AuthContext = React.createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = React.useState(null)
  // Start in a loading state only when there is a token to validate, so a
  // logged-out visitor lands on the login screen without an extra flash.
  const [loading, setLoading] = React.useState(() => Boolean(getToken()))

  const logout = React.useCallback(() => {
    setAuthToken(null)
    setUser(null)
  }, [])

  // A 401 from any request means our session is dead — drop it everywhere.
  React.useEffect(() => {
    setUnauthorizedHandler(() => setUser(null))
    return () => setUnauthorizedHandler(null)
  }, [])

  // Restore the session from a persisted token on first load.
  React.useEffect(() => {
    if (!getToken()) return
    let active = true
    authApi
      .me()
      .then((u) => active && setUser(u))
      .catch(() => active && setAuthToken(null))
      .finally(() => active && setLoading(false))
    return () => {
      active = false
    }
  }, [])

  const login = React.useCallback(async (credentials) => {
    const { access_token } = await authApi.login(credentials)
    setAuthToken(access_token)
    const u = await authApi.me()
    setUser(u)
    return u
  }, [])

  const register = React.useCallback(
    async (payload) => {
      await authApi.register(payload)
      return login({ email: payload.email, password: payload.password })
    },
    [login],
  )

  const value = { user, loading, login, register, logout }
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

// Co-locating the hook with its provider is the standard React Context pattern.
// eslint-disable-next-line react-refresh/only-export-components
export function useAuth() {
  const ctx = React.useContext(AuthContext)
  if (ctx === null) throw new Error('useAuth must be used within an AuthProvider')
  return ctx
}
