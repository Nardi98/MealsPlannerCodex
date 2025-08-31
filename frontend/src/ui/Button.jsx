import React from 'react'

export default function Button({ variant = 'primary', children, Icon, className = '', ...props }) {
  const map = {
    primary: { bg: 'var(--c-pos)', fg: '#fff' },
    danger: { bg: 'var(--c-neg)', fg: '#fff' },
    a1: { bg: 'var(--c-a1)', fg: '#fff' },
    a2: { bg: 'var(--c-a2)', fg: '#fff' },
    ghost: { bg: 'transparent', fg: 'var(--text-strong)' },
  }[variant] || { bg: 'var(--c-pos)', fg: '#fff' }
  return (
    <button
      {...props}
      className={`inline-flex items-center gap-2 rounded-2xl px-3 py-2 text-sm shadow-sm hover:opacity-95 ${className}`}
      style={{ backgroundColor: map.bg, color: map.fg }}
    >
      {Icon && <Icon className="h-5 w-5" />} {children}
    </button>
  )
}
