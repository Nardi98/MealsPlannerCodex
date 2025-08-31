import React from 'react'

export default function NavItem({ active, Icon, label, onClick, className = '' }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex w-full items-center gap-3 rounded-lg px-4 py-2 text-left hover:opacity-95 ${
        active ? 'text-white' : 'text-[var(--text-strong)]'
      } ${className}`}
      style={{ backgroundColor: active ? 'var(--c-a1)' : 'transparent' }}
    >
      {Icon && <Icon className="h-5 w-5" />} <span className="text-sm font-medium">{label}</span>
    </button>
  )
}
