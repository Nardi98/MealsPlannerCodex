import React from 'react';

export default function Button({ children, variant = 'primary', size = 'md', className = '', style = {}, ...props }) {
  const baseStyle = {
    borderRadius: '1rem',
    padding: size === 'sm' ? '0.25rem 0.5rem' : size === 'lg' ? '0.75rem 1rem' : '0.5rem 0.75rem',
    fontSize: size === 'sm' ? '0.75rem' : size === 'lg' ? '1rem' : '0.875rem',
    border: 'none',
    cursor: 'pointer',
  };
  const variants = {
    primary: { backgroundColor: 'var(--c-a1)', color: 'white' },
    a2: { backgroundColor: 'var(--c-a2)', color: 'var(--text-strong)' },
    danger: { backgroundColor: 'var(--c-neg)', color: 'white' },
    ghost: { backgroundColor: 'transparent', color: 'var(--text-strong)', border: '1px solid var(--border)' },
  };
  return (
    <button
      {...props}
      className={className}
      style={{ ...baseStyle, ...(variants[variant] || variants.primary), ...style }}
    >
      {children}
    </button>
  );
}
