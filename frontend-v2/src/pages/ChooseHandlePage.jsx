import React from 'react'
import UsernameField from '../components/UsernameField'

/**
 * Mandatory one-time handle confirmation (UN-5 / UN-6 / UN-7).
 *
 * Reached only through `Gate`, which shows it instead of the whole app while
 * `user.username_confirmed` is not true. It must never render the provisional,
 * system-assigned handle: that handle is derived from the email local part, so
 * displaying it before confirmation would disclose part of the address (UN-11).
 *
 * Stub placed by Phase 3.0 wiring; the real implementation belongs to 3C.
 * Route component — takes no props.
 */
export function ChooseHandlePage() {
  const [value, setValue] = React.useState('')

  return (
    <div
      className="flex items-center justify-center"
      style={{ minHeight: '100vh', padding: 20 }}
    >
      <div style={{ width: '100%', maxWidth: 420 }}>
        <h1
          style={{
            fontFamily: 'var(--font-display)',
            fontSize: 'var(--text-xl)',
            fontWeight: 'var(--weight-semibold)',
            color: 'var(--text-strong)',
            margin: '0 0 8px',
          }}
        >
          Choose your username
        </h1>
        <p style={{ margin: '0 0 16px', fontSize: 'var(--text-sm)', color: 'var(--text-muted)' }}>
          This is the name shown when you share a recipe. Pick one to continue.
        </p>
        <UsernameField value={value} onChange={setValue} error="" />
      </div>
    </div>
  )
}

export default ChooseHandlePage
