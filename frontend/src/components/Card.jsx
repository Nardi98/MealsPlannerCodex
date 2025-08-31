import React from 'react';

export function Card({ children, className='', ...props }) {
  return (
    <div
      className={`rounded-2xl border bg-white p-4 shadow-sm ${className}`}
      style={{ borderColor: 'var(--border)' }}
      {...props}
    >
      {children}
    </div>
  );
}
