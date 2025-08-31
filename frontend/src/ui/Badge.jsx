import React from 'react'

export default function Badge({ tone = 'a3', children, className = '' }) {
  const fg = `var(--c-${tone})`
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs ${className}`}
      style={{ backgroundColor: `color-mix(in srgb, ${fg} 14%, transparent)`, color: fg }}
    >
      {children}
    </span>
  )
}
