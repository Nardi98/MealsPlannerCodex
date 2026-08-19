import React from 'react'

/**
 * Recipes other people shared with this account (SWM-1 / SWM-2 / SWM-3).
 *
 * Stub placed by Phase 3.0 wiring; the real implementation belongs to 3B.
 * Route component — takes no props.
 */
export function SharedWithMePage() {
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
        Shared with me
      </h1>
      <p style={{ marginTop: 8, color: 'var(--text-muted)', fontSize: 'var(--text-sm)' }}>
        Nothing has been shared with you yet.
      </p>
    </section>
  )
}

export default SharedWithMePage
