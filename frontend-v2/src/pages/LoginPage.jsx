import React from 'react'
import { Button, Card, Input } from '../components'
import GoogleSignInButton from '../components/GoogleSignInButton'
import { useAuth } from '../auth/AuthContext'

export default function LoginPage() {
  const { login, register, loginWithGoogle } = useAuth()
  const [mode, setMode] = React.useState('login') // 'login' | 'register'
  const [email, setEmail] = React.useState('')
  const [password, setPassword] = React.useState('')
  const [displayName, setDisplayName] = React.useState('')
  const [error, setError] = React.useState('')
  const [busy, setBusy] = React.useState(false)

  const isRegister = mode === 'register'

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setBusy(true)
    try {
      if (isRegister) {
        await register({ email, password, display_name: displayName || null })
      } else {
        await login({ email, password })
      }
    } catch (err) {
      setError(err.message || 'Something went wrong. Please try again.')
    } finally {
      setBusy(false)
    }
  }

  const handleGoogleCredential = async (credential) => {
    setError('')
    setBusy(true)
    try {
      await loginWithGoogle(credential)
    } catch (err) {
      setError(err.message || 'Google sign-in failed. Please try again.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div
      className="flex items-center justify-center"
      style={{ minHeight: '100vh', padding: 20, background: 'var(--surface-page)' }}
    >
      <Card style={{ width: '100%', maxWidth: 380 }}>
        <div className="flex flex-col items-center" style={{ marginBottom: 20 }}>
          <img
            src="/assets/Logo_mealplanner.png"
            alt="Meal Planner logo"
            style={{ height: 48, opacity: 0.9 }}
          />
          <h1
            style={{
              fontFamily: 'var(--font-display)',
              fontWeight: 'var(--weight-medium)',
              fontSize: 20,
              color: 'var(--text-strong)',
              marginTop: 12,
            }}
          >
            {isRegister ? 'Create your account' : 'Welcome back'}
          </h1>
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col gap-3">
          {isRegister && (
            <label className="flex flex-col gap-1">
              <span style={{ fontSize: 13, color: 'var(--text-muted)' }}>Name</span>
              <Input
                type="text"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                autoComplete="name"
              />
            </label>
          )}
          <label className="flex flex-col gap-1">
            <span style={{ fontSize: 13, color: 'var(--text-muted)' }}>Email</span>
            <Input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="email"
              required
            />
          </label>
          <label className="flex flex-col gap-1">
            <span style={{ fontSize: 13, color: 'var(--text-muted)' }}>Password</span>
            <Input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete={isRegister ? 'new-password' : 'current-password'}
              required
            />
          </label>

          {error && (
            <div role="alert" style={{ fontSize: 13, color: 'var(--c-neg)' }}>
              {error}
            </div>
          )}

          <Button type="submit" variant="primary" disabled={busy} className="justify-center">
            {isRegister ? 'Sign up' : 'Log in'}
          </Button>
        </form>

        <div className="flex items-center gap-3" style={{ margin: '16px 0' }}>
          <div style={{ flex: 1, height: 1, background: 'var(--border-default)' }} />
          <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>or</span>
          <div style={{ flex: 1, height: 1, background: 'var(--border-default)' }} />
        </div>

        <GoogleSignInButton onCredential={handleGoogleCredential} />

        <div style={{ textAlign: 'center', marginTop: 16, fontSize: 13 }}>
          <button
            type="button"
            onClick={() => {
              setMode(isRegister ? 'login' : 'register')
              setError('')
            }}
            style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--c-a2)' }}
          >
            {isRegister ? 'Already have an account? Log in' : 'Create an account'}
          </button>
        </div>
      </Card>
    </div>
  )
}
