import React from 'react';

export default function Badge({ children, tone = 'a3', className = '', style = {} }) {
  const tones = {
    a2: { backgroundColor: 'var(--c-a2)', color: 'var(--text-strong)' },
    a3: { backgroundColor: 'var(--c-a3)', color: 'white' },
  };
  const base = {
    display: 'inline-block',
    borderRadius: '9999px',
    padding: '0.125rem 0.5rem',
    fontSize: '0.75rem',
    lineHeight: 1,
  };
  return (
    <span className={className} style={{ ...base, ...(tones[tone] || tones.a3), ...style }}>
      {children}
    </span>
  );
}
