import React from 'react'

export const Card = React.forwardRef(function Card(
  { children, className = '', style = {}, ...props },
  ref,
) {
  return (
    <div
      ref={ref}
      {...props}
      className={`bg-white p-4 shadow-sm ${className}`}
      style={{
        borderRadius: 'var(--radius-lg)',
        border: '1px solid var(--border-default)',
        boxShadow: 'var(--shadow-sm)',
        ...style,
      }}
    >
      {children}
    </div>
  )
})
