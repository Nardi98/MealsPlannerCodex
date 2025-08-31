import React from 'react'

export function NavItem({ variant = 'default', size = 'md', Icon, label, className = '', ...props }) {
  const sizeMap = {
    sm: 'px-2 py-1 text-sm',
    md: 'px-3 py-2 text-sm',
    lg: 'px-4 py-3 text-base',
  }[size]
  const active = variant === 'active'

  return (
    <button
      type="button"
      className={`w-full text-left flex items-center gap-3 rounded-xl hover:opacity-95 ${sizeMap} ${active ? 'text-white' : 'text-[color:var(--text-strong)]'} ${className}`}
      style={{ backgroundColor: active ? 'var(--c-a1)' : 'transparent' }}
      {...props}
    >
      {Icon && <Icon className="h-5 w-5" />}
      <span className="font-medium">{label}</span>
    </button>
  )
}
