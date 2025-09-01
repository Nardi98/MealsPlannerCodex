import React from 'react';

export default function NavItem({ active = false, Icon, label, onClick, className = '', style = {}, ...props }) {
  const base = 'w-full text-left flex items-center gap-3 rounded-xl px-3 py-2 hover:opacity-95';
  const textClass = active ? 'text-white' : 'text-[color:var(--text-strong)]';
  return (
    <button
      type="button"
      onClick={onClick}
      {...props}
      className={`${base} ${textClass} ${className}`.trim()}
      style={{ backgroundColor: active ? 'var(--c-a1)' : 'transparent', ...style }}
    >
      {Icon && <Icon className="h-5 w-5" />}
      <span className="text-sm font-medium">{label}</span>
    </button>
  );
}
