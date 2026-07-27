import React from 'react'
import { Link } from 'react-router-dom'
import { Button, Input } from '../components'
import { authApi } from '../api/authApi'
import { AuthCard } from './LoginPage'

// Requests a password-reset email. The server always answers neutrally, so we
// show the same confirmation whether or not the address exists.
export default function ForgotPasswordPage() {
  const [email, setEmail] = React.useState('')
  const [sent, setSent] = React.useState(false)
  const [busy, setBusy] = React.useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setBusy(true)
    try {
      await authApi.forgotPassword(email)
    } catch {
      // Neutral by design — never reveal whether the email is registered.
    } finally {
      setBusy(false)
      setSent(true)
    }
  }

  if (sent) {
    return (
      <AuthCard title="Check your email">
        <p style={{ fontSize: 14, color: 'var(--text-muted)', textAlign: 'center' }}>
          If an account exists for <strong>{email}</strong>, we&rsquo;ve sent a
          link to reset your password.
        </p>
        <Link to="/">
          <Button variant="primary" className="justify-center" style={{ width: '100%', marginTop: 20 }}>
            Back to log in
          </Button>
        </Link>
      </AuthCard>
    )
  }

  return (
    <AuthCard title="Reset your password">
      <p style={{ fontSize: 14, color: 'var(--text-muted)', textAlign: 'center', marginBottom: 16 }}>
        Enter your email and we&rsquo;ll send you a reset link.
      </p>
      <form onSubmit={handleSubmit} className="flex flex-col gap-3">
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
        <Button type="submit" variant="primary" disabled={busy} className="justify-center">
          Send reset link
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
