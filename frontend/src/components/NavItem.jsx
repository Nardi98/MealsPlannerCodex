import React from 'react';

export default function NavItem({ active, label, onClick, className = '' }) {
  const base = {
    display: 'flex',
    alignItems: 'center',
    gap: '0.75rem',
    borderRadius: '0.75rem',
    padding: '0.5rem 0.75rem',
    cursor: 'pointer',
    backgroundColor: active ? 'var(--c-a1)' : 'transparent',
    color: active ? 'white' : 'var(--text-strong)',
  };
  return (
    <button type="button" onClick={onClick} className={className} style={base}>
      <span className="text-sm font-medium">{label}</span>
    </button>
  );
}
