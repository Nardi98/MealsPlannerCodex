import React from 'react'

export default function Card({ children, className = '' }) {
  return (
    <div
      className={`rounded-lg border bg-white p-4 shadow-sm ${className}`}
      style={{ borderColor: 'var(--border)' }}
    >
      {children}
    </div>
  )
}
