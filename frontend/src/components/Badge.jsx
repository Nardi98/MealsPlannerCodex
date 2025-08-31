import React from 'react'

export function Badge({ variant = 'a3', size = 'md', children, className = '', ...props }) {
  const fg = `var(--c-${variant})`
  const sizeMap = { sm: 'px-1.5 py-0 text-xs', md: 'px-2 py-0.5 text-xs', lg: 'px-2.5 py-1 text-sm' }[size]

  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full ${sizeMap} ${className}`}
      style={{ backgroundColor: `color-mix(in srgb, ${fg} 14%, transparent)`, color: fg }}
      {...props}
    >
      {children}
    </span>
  )
}
