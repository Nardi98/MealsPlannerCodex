import React from 'react'
import { Input } from './Input'

/**
 * Username input with availability feedback (UN-5 / UN-6 / UN-7).
 *
 * Stub placed by Phase 3.0 wiring; the real implementation (debounced
 * availability check) belongs to 3C.
 * Prop signature is fixed: ({ value, onChange, error }).
 * `onChange` receives the raw string value, not the DOM event.
 */
export function UsernameField({ value, onChange, error }) {
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
        value={value ?? ''}
        onChange={(event) => onChange?.(event.target.value)}
        aria-invalid={error ? 'true' : undefined}
      />
      {error && (
        <p role="alert" style={{ margin: 0, fontSize: 12, color: 'var(--c-neg)' }}>
          {error}
        </p>
      )}
    </div>
  )
}

export default UsernameField
