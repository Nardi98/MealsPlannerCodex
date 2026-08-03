import React from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { Button } from '../components'
import { authApi } from '../api/authApi'
import { AuthCard } from './LoginPage'

// Confirms an email address from the token in the verification link, then points
// the user back to log in.
export default function VerifyEmailPage() {
  const [params] = useSearchParams()
  const token = params.get('token')
  const [status, setStatus] = React.useState('pending') // 'pending' | 'ok' | 'error'
  const [error, setError] = React.useState('')

  React.useEffect(() => {
    if (!token) {
      setStatus('error')
      setError('This verification link is missing its token.')
      return
    }
    let active = true
    authApi
      .verifyEmail(token)
      .then(() => active && setStatus('ok'))
      .catch((err) => {
        if (!active) return
        setStatus('error')
        setError(err.message || 'We could not verify this link.')
      })
    return () => {
      active = false
    }
  }, [token])

  const body = {
    pending: 'Verifying your email…',
    ok: 'Your email is verified. You can now log in.',
    error: error,
  }[status]

  return (
    <AuthCard title="Verify your email">
      <p
        role={status === 'error' ? 'alert' : undefined}
        style={{
          fontSize: 14,
          textAlign: 'center',
          color: status === 'error' ? 'var(--c-neg)' : 'var(--text-muted)',
        }}
      >
        {body}
      </p>
      {status !== 'pending' && (
        <Link to="/">
          <Button variant="primary" className="justify-center" style={{ width: '100%', marginTop: 20 }}>
            Go to log in
          </Button>
        </Link>
      )}
    </AuthCard>
  )
}
