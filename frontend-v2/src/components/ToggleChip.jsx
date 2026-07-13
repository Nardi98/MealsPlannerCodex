import React from 'react'

/**
 * A small pill-shaped toggle button. Used for category selection and section
 * filtering. `active` drives the accent styling; `children` is the label.
 */
export default function ToggleChip({ active, onClick, label, children }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      aria-label={label}
      className="rounded-full px-2.5 py-1 text-xs border transition-colors"
      style={{
        borderColor: active ? 'var(--c-a2)' : 'var(--border)',
        backgroundColor: active
          ? 'color-mix(in srgb, var(--c-a2) 14%, transparent)'
          : 'transparent',
        color: active ? 'var(--c-a2)' : 'var(--text-subtle)',
      }}
    >
      {children}
    </button>
  )
}
