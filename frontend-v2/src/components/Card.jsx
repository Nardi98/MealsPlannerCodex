import React from 'react'

export const Card = React.forwardRef(function Card(
  { children, className = '', ...props },
  ref,
) {
  return (
    <div
      ref={ref}
      {...props}
      className={`rounded-2xl border bg-white p-4 shadow-sm ${className}`}
      style={{ borderColor: 'var(--border)' }}
    >
      {children}
    </div>
  )
})
