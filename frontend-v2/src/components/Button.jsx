export function Button({ variant='primary', size='md', Icon, children, className='', ...props }) {
  const map = {
    primary:   { bg: 'var(--c-pos)', fg: '#fff' },
    danger:    { bg: 'var(--c-neg)', fg: '#fff' },
    accent:    { bg: 'var(--c-a2)', fg: 'var(--text-on-accent)' },
    secondary: { bg: 'var(--c-a1)', fg: '#fff' },
    // Legacy aliases kept so existing pages keep working.
    a1:        { bg: 'var(--c-a1)', fg: '#fff' },
    a2:        { bg: 'var(--c-a2)', fg: 'var(--text-on-accent)' },
    ghost:     { bg: 'transparent', fg: 'var(--text-strong)', border: 'var(--border)' },
  }[variant]
  // Design guide §8.4: 44px is the floor for a tap target, in both dimensions.
  // The width matters for the single-character buttons -- the shopping list's
  // people steppers were 44 tall and 28 wide. Text labels are wider than the
  // minimum anyway, so it costs them nothing. `sm` is reserved for dense inline
  // rows and gets 36px, still finger-sized.
  const sizeMap = {
    sm: 'min-h-9 min-w-9 px-2 py-1 text-xs',
    md: 'min-h-11 min-w-11 px-3 py-2 text-sm',
    lg: 'min-h-11 min-w-11 px-4 py-2.5 text-sm',
  }[size]

  return (
    <button type="button"
      className={`inline-flex items-center justify-center gap-2 shadow-sm hover:opacity-95 border font-[family:var(--font-display)] ${sizeMap} ${className}`}
      style={{ backgroundColor: map?.bg, color: map?.fg, borderColor: map?.border || 'transparent', borderRadius: 'var(--radius-md)' }}
      {...props}>
      {Icon && <Icon className="h-5 w-5" />}{children}
    </button>
  )
}
