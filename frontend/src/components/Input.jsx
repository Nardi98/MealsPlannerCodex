import React from 'react';

export default function Input({ className = '', style = {}, ...props }) {
  const base = 'rounded-xl border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[color:var(--c-a2)]';
  return (
    <input
      {...props}
      className={`${base} ${className}`.trim()}
      style={{ borderColor: 'var(--border)', color: 'var(--text-strong)', ...style }}
    />
  );
}
