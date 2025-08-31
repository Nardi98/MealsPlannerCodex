import React from 'react';

export function NavItem({ active, Icon, label, onClick, className='', ...props }) {
  return (
    <button
      onClick={onClick}
      className={`w-full text-left flex items-center gap-3 rounded-xl px-3 py-2 hover:opacity-95 ${active ? 'text-white' : 'text-[color:var(--text-strong)]'} ${className}`}
      style={{ backgroundColor: active ? 'var(--c-a1)' : 'transparent' }}
      type="button"
      {...props}
    >
      {Icon && <Icon className="h-5 w-5" />}
      <span className="text-sm font-medium">{label}</span>
    </button>
  );
}
