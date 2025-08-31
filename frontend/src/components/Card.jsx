import React from 'react';

export default function Card({ children, className = '', style = {}, ...props }) {
  const base = {
    backgroundColor: 'var(--c-white)',
    border: '1px solid var(--border)',
    borderRadius: '1rem',
    boxShadow: '0 1px 2px rgba(0,0,0,0.05)',
    padding: '1rem',
  };
  return (
    <div className={className} style={{ ...base, ...style }} {...props}>
      {children}
    </div>
  );
}
