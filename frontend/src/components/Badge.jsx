import React from 'react';

const TONE_STYLES = {
  pos: { backgroundColor: 'var(--c-pos)', color: 'white' },
  neg: { backgroundColor: 'var(--c-neg)', color: 'white' },
  a1: { backgroundColor: 'var(--c-a1)', color: 'white' },
  a2: { backgroundColor: 'var(--c-a2)', color: 'var(--text-strong)' },
  a3: { backgroundColor: 'var(--c-a3)', color: 'white' },
};

export default function Badge({ tone = 'a3', className = '', style = {}, children, ...props }) {
  const base = 'inline-flex items-center rounded-xl px-2 py-1 text-xs font-medium';
  const toneStyle = TONE_STYLES[tone] || TONE_STYLES.a3;
  return (
    <span
      {...props}
      className={`${base} ${className}`.trim()}
      style={{ ...toneStyle, ...style }}
    >
      {children}
    </span>
  );
}
