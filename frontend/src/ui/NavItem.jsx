import React from 'react'

export default function NavItem({ active, Icon, label, onClick, className = '' }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`w-full text-left flex items-center gap-3 rounded-xl px-3 py-2 hover:opacity-95 ${
        active ? 'text-white' : 'text-[var(--text-strong)]'
      } ${className}`}
      style={{ backgroundColor: active ? 'var(--c-a1)' : 'transparent' }}
    >
      {Icon && <Icon className="h-5 w-5" />} <span className="text-sm font-medium">{label}</span>
    </button>
  )
}
