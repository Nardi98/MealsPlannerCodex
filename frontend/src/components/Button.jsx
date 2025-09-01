import React from 'react';

const SIZE_CLASSES = {
  sm: 'px-2.5 py-1.5 text-xs',
  md: 'px-3 py-2 text-sm',
  lg: 'px-4 py-2.5 text-base',
};

const VARIANT_STYLES = {
  primary: { backgroundColor: 'var(--c-pos)', color: 'white' },
  danger: { backgroundColor: 'var(--c-neg)', color: 'white' },
  a1: { backgroundColor: 'var(--c-a1)', color: 'white' },
  a2: { backgroundColor: 'var(--c-a2)', color: 'var(--text-strong)' },
  ghost: { backgroundColor: 'transparent', color: 'var(--text-strong)', borderColor: 'var(--border)' },
};

export default function Button({
  variant = 'primary',
  size = 'md',
  className = '',
  style = {},
  children,
  ...props
}) {
  const base = 'inline-flex items-center justify-center gap-2 rounded-2xl font-medium hover:opacity-95 focus:outline-none focus:ring-2 focus:ring-[color:var(--c-a2)]';
  const sizeClass = SIZE_CLASSES[size] || SIZE_CLASSES.md;
  const variantStyle = VARIANT_STYLES[variant] || VARIANT_STYLES.primary;
  const borderClass = variant === 'ghost' ? 'border' : '';

  return (
    <button
      type="button"
      {...props}
      className={`${base} ${sizeClass} ${borderClass} ${className}`.trim()}
      style={{ ...variantStyle, ...style }}
    >
      {children}
    </button>
  );
}
