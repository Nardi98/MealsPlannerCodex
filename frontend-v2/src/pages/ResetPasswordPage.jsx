import React from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { Button, Input } from '../components'
import { authApi, validatePassword } from '../api/authApi'
import { AuthCard } from './LoginPage'

// Sets a new password from the token in the reset link, enforcing the same
// password policy as the server.
export default function ResetPasswordPage() {
  const [params] = useSearchParams()
  const token = params.get('token')
  const [password, setPassword] = React.useState('')
  const [confirm, setConfirm] = React.useState('')
  const [error, setError] = React.useState('')
  const [busy, setBusy] = React.useState(false)
  const [done, setDone] = React.useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    if (!token) {
      setError('This reset link is missing its token.')
      return
    }
    const pwError = validatePassword(password)
    if (pwError) {
      setError(pwError)
      return
    }
    if (password !== confirm) {
      setError('Passwords do not match.')
      return
    }
    setBusy(true)
    try {
      await authApi.resetPassword(token, password)
      setDone(true)
    } catch (err) {
      setError(err.message || 'We could not reset your password.')
    } finally {
      setBusy(false)
    }
  }

  if (done) {
    return (
      <AuthCard title="Password updated">
        <p style={{ fontSize: 14, color: 'var(--text-muted)', textAlign: 'center' }}>
          Your password has been reset. You can now log in with it.
        </p>
        <Link to="/">
          <Button variant="primary" className="justify-center" style={{ width: '100%', marginTop: 20 }}>
            Go to log in
          </Button>
        </Link>
      </AuthCard>
    )
  }

  return (
    <AuthCard title="Choose a new password">
      <form onSubmit={handleSubmit} className="flex flex-col gap-3">
        <label className="flex flex-col gap-1">
          <span style={{ fontSize: 13, color: 'var(--text-muted)' }}>New password</span>
          <Input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="new-password"
            required
          />
          <span style={{ fontSize: 12, color: 'var(--text-subtle)' }}>
            At least 8 characters with an uppercase letter, a lowercase letter,
            and a digit.
          </span>
        </label>
        <label className="flex flex-col gap-1">
          <span style={{ fontSize: 13, color: 'var(--text-muted)' }}>Confirm password</span>
          <Input
            type="password"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            autoComplete="new-password"
            required
          />
        </label>

        {error && (
          <div role="alert" style={{ fontSize: 13, color: 'var(--c-neg)' }}>
            {error}
          </div>
        )}

        <Button type="submit" variant="primary" disabled={busy} className="justify-center">
          Reset password
        </Button>
      </form>
      <div style={{ textAlign: 'center', marginTop: 16, fontSize: 13 }}>
        <Link to="/" style={{ color: 'var(--c-a2)' }}>
          Back to log in
        </Link>
      </div>
    </AuthCard>
  )
}
