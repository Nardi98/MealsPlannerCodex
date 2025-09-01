import React from 'react';

export default function NavItem({
  active = false,
  disabled = false,
  Icon,
  label,
  onClick,
  className = '',
  style = {},
  ...props
}) {
  const base = 'w-full text-left flex items-center gap-3 rounded-xl px-3 py-2';
  const hoverClass = disabled ? '' : 'hover:opacity-95';
  const textClass = active
    ? 'text-white'
    : disabled
      ? 'text-[color:var(--text-muted)]'
      : 'text-[color:var(--text-strong)]';
  const cursorClass = disabled ? 'cursor-not-allowed' : '';

  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      {...props}
      className={`${base} ${hoverClass} ${textClass} ${cursorClass} ${className}`.trim()}
      style={{
        backgroundColor: active ? 'var(--c-a1)' : 'transparent',
        opacity: disabled ? 0.4 : 1,
        ...style,
      }}
    >
      {Icon && <Icon className="h-5 w-5" />}
      <span className="text-sm font-medium">{label}</span>
    </button>
  );
}
