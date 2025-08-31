import React from 'react';

export default function Input({ className = '', style = {}, ...props }) {
  const base = {
    border: '1px solid var(--border)',
    borderRadius: '0.75rem',
    padding: '0.5rem 0.5rem',
    fontSize: '0.875rem',
  };
  return <input className={className} style={{ ...base, ...style }} {...props} />;
}
