import React from 'react'
import { useParams } from 'react-router-dom'

/**
 * In-app landing for a share link (SP-3): reads `:token` and, once
 * authenticated, copies the recipe via POST /s/{token}/copy.
 *
 * Stub placed by Phase 3.0 wiring; the real implementation belongs to 3B.
 * Route component — takes no props; the token comes from `useParams`.
 */
export function SharedRecipePage() {
  const { token } = useParams()

  return (
    <section>
      <h1
        style={{
          fontFamily: 'var(--font-display)',
          fontSize: 'var(--text-xl)',
          fontWeight: 'var(--weight-semibold)',
          color: 'var(--text-strong)',
          margin: 0,
        }}
      >
        Shared recipe
      </h1>
      <p style={{ marginTop: 8, color: 'var(--text-muted)', fontSize: 'var(--text-sm)' }}>
        {token ? 'Loading the shared recipe…' : 'This share link is missing its token.'}
      </p>
    </section>
  )
}

export default SharedRecipePage
