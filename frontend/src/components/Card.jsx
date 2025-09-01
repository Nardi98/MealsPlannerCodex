import React from 'react';

export default function Card({ className = '', style = {}, children, ...props }) {
  const base = 'rounded-2xl border bg-white shadow-sm';
  return (
    <div
      {...props}
      className={`${base} ${className}`.trim()}
      style={{ borderColor: 'var(--border)', ...style }}
    >
      {children}
    </div>
  );
}
