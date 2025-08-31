import React from 'react'

export default function Input({ className = '', ...props }) {
  return (
    <input
      {...props}
      className={`rounded-lg border px-4 py-2 text-sm focus:outline-none ${className}`}
      style={{ borderColor: 'var(--border)', color: 'var(--text-strong)' }}
    />
  )
}
