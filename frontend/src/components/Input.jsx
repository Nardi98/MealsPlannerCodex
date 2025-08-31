import React from 'react'

export function Input({ variant = 'default', size = 'md', className = '', ...props }) {
  const sizeMap = {
    sm: 'px-2 py-1 text-sm',
    md: 'px-3 py-2 text-sm',
    lg: 'px-4 py-2.5 text-base',
  }[size]
  const variantMap = {
    default: 'bg-white',
    ghost: 'bg-transparent',
  }[variant]

  return (
    <input
      className={`rounded-xl border focus:outline-none focus:ring-2 focus:ring-[color:var(--c-a2)] ${variantMap} ${sizeMap} ${className}`}
      style={{ borderColor: 'var(--border)', color: 'var(--text-strong)' }}
      {...props}
    />
  )
}
