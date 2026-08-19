import React from 'react'
import { Button, Card } from '../components'
import UsernameField from '../components/UsernameField'
import { useAuth } from '../auth/AuthContext'
import { authApi } from '../api/authApi'

/**
 * Mandatory one-time handle confirmation (UN-5 / UN-6 / UN-7 / UN-11).
 *
 * Reached only through `Gate`, which shows this and nothing else while
 * `user.username_confirmed` is not true. There is no route to it and no route
 * out of it: the only exit is confirming a handle, which flips the flag the
 * gate reads.
 *
 * UN-11. The account already *has* a handle — one D-7 derived from the email
 * local part (anna.rossi@… → anna_rossi). This page must never render it: not
 * in the field, not as a placeholder, not as a suggestion. Doing so would put a
 * slice of the address on screen at the exact moment the gate exists to keep it
 * off. Hence the field starts empty, nothing here reads `user.username` or
 * `user.email`, and failure messages are server text about the *handle* only.
 *
 * Submitting calls `authApi.confirmUsername` → `POST /auth/username`, which is
 * **confirm-once**: it stamps `username_changed_at`, which is what
 * `username_confirmed` derives from and therefore what releases the gate. A 403
 * means the handle was already confirmed — *changing* a handle (UN-8/UN-9) is
 * still deferred to Part 2, so this route is the only writer and it writes once.
 *
 * The `typeof confirm !== 'function'` guard below is kept deliberately: it is
 * what turned a permanently-trapped Google sign-up into a legible message while
 * the endpoint was missing, and it costs one comparison to stay safe if a build
 * ever ships a client ahead of the server.
 */
export function ChooseHandlePage() {
  const { refreshUser } = useAuth()
  const [value, setValue] = React.useState('')
  const [error, setError] = React.useState('')
  const [busy, setBusy] = React.useState(false)

  const handle = value.trim().toLowerCase()

  const handleSubmit = async (event) => {
    event.preventDefault()
    setError('')

    const confirm = authApi.confirmUsername
    if (typeof confirm !== 'function') {
      setError(
        'Saving your username is not available yet. Please try again later.'
      )
      return
    }

    setBusy(true)
    try {
      await confirm(handle)
      // The gate keys off `username_confirmed`, so re-reading the account is
      // what actually releases the app.
      await refreshUser()
    } catch (err) {
      // Server text about the handle (e.g. "That username is taken"). It is
      // never logged, and it never mentions the account's email.
      setError(err.message || 'That username could not be saved. Please try again.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div
      className="flex items-center justify-center"
      style={{ minHeight: '100vh', padding: 20, background: 'var(--surface-page)' }}
    >
      <Card style={{ width: '100%', maxWidth: 420 }}>
        <h1
          style={{
            fontFamily: 'var(--font-display)',
            fontWeight: 'var(--weight-medium)',
            fontSize: 20,
            color: 'var(--text-strong)',
            margin: '0 0 8px',
          }}
        >
          Choose your username
        </h1>
        <p
          style={{
            margin: '0 0 20px',
            fontSize: 14,
            color: 'var(--text-muted)',
          }}
        >
          This is the name shown to other people when you share a recipe. Pick
          one to continue.
        </p>

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <UsernameField value={value} onChange={setValue} error={error} />
          <Button
            type="submit"
            variant="primary"
            className="justify-center"
            disabled={busy || handle.length === 0}
          >
            Continue
          </Button>
        </form>
      </Card>
    </div>
  )
}

export default ChooseHandlePage
