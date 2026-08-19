import React from 'react'
import { Input } from './Input'
import { authApi } from '../api/authApi'

/**
 * Username input with availability feedback (UN-5 / UN-6 / UN-7).
 *
 * Prop signature is fixed: ({ value, onChange, error }).
 * `onChange` receives the raw string value, not the DOM event.
 *
 * The parent stays the authority on the value and on hard errors: `error` is
 * whatever the *submit* produced (a 409 from register, say). Everything this
 * component discovers on its own is advisory and lives in the status line, so a
 * failed or throttled check can never masquerade as a rejected handle.
 */

// The server allows 30 checks per minute per caller. Debouncing well past a
// typing burst keeps an ordinary registration to a couple of requests, so the
// limit is a backstop rather than something users meet (UN-7).
const DEBOUNCE_MS = 400

// `usernames.MIN_LENGTH`. Below it the answer is always "too short", which the
// hint already says — no point spending a request to hear it.
const MIN_LENGTH = 3

// Mirrors `usernames.normalise`: UN-3 lowercases on entry rather than rejecting
// for case, so the handle asked about is the handle that would be created.
function normalise(value) {
  return (value ?? '').trim().toLowerCase()
}

// The endpoint answers with codes, not sentences, for "taken" and "reserved" —
// deliberately, so it never says *who* holds a handle. Both become the same
// shape of message here; a validation `reason` is already user-facing prose and
// is shown as-is.
function describe(reason) {
  if (reason === 'taken') return 'That username is already taken.'
  if (reason === 'reserved') return 'That username is not available.'
  return reason || 'That username is not available.'
}

export function UsernameField({ value, onChange, error }) {
  // null = nothing to say yet. Otherwise { tone, message }, where tone is
  // 'ok' | 'bad' | 'muted' and only 'bad' means the handle itself is refused.
  const [status, setStatus] = React.useState(null)

  const candidate = normalise(value)

  React.useEffect(() => {
    if (candidate.length < MIN_LENGTH) {
      setStatus(null)
      return undefined
    }

    // Guards against a slow answer for an abandoned handle overwriting the
    // answer for the current one.
    let current = true
    const timer = setTimeout(() => {
      setStatus({ tone: 'muted', message: 'Checking…' })
      authApi
        .checkUsername(candidate)
        .then((result) => {
          if (!current) return
          setStatus(
            result && result.available
              ? { tone: 'ok', message: 'That username is available.' }
              : { tone: 'bad', message: describe(result && result.reason) }
          )
        })
        .catch((err) => {
          if (!current) return
          // Never fatal: the handle is still checked for real at submit. The
          // message is not logged — it can echo attacker-controlled input.
          // 429, not the message text. `client.js` attaches the status to
          // everything it throws, and the status is the part the backend has
          // promised — the prose is free to be reworded or translated, and a
          // proxy's own 429 body would not have said "rate limit" at all.
          const throttled = err?.status === 429
          setStatus({
            tone: 'muted',
            message: throttled
              ? 'Too many checks just now — try again in a moment.'
              : 'Could not check that username right now.',
          })
        })
    }, DEBOUNCE_MS)

    return () => {
      current = false
      clearTimeout(timer)
    }
  }, [candidate])

  const statusColor =
    status && status.tone === 'ok'
      ? 'var(--c-pos)'
      : status && status.tone === 'bad'
        ? 'var(--c-neg)'
        : 'var(--text-muted)'

  return (
    <div className="flex flex-col gap-1">
      <label
        htmlFor="username-field"
        style={{
          fontFamily: 'var(--font-body)',
          fontSize: 'var(--text-sm)',
          color: 'var(--text-strong)',
        }}
      >
        Username
      </label>
      <Input
        id="username-field"
        name="username"
        type="text"
        value={value ?? ''}
        onChange={(event) => onChange?.(event.target.value)}
        autoComplete="username"
        autoCapitalize="none"
        spellCheck={false}
        maxLength={30}
        aria-invalid={error || (status && status.tone === 'bad') ? 'true' : undefined}
        aria-describedby="username-field-hint"
      />
      <p
        id="username-field-hint"
        style={{ margin: 0, fontSize: 12, color: 'var(--text-subtle)' }}
      >
        3–30 lowercase letters, numbers, or underscores. Shown on recipes you
        share.
      </p>
      {status && (
        <p role="status" style={{ margin: 0, fontSize: 12, color: statusColor }}>
          {status.message}
        </p>
      )}
      {error && (
        <p role="alert" style={{ margin: 0, fontSize: 12, color: 'var(--c-neg)' }}>
          {error}
        </p>
      )}
    </div>
  )
}

export default UsernameField
