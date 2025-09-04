export function Button({ variant='primary', size='md', Icon, children, className='', ...props }) {
  const map = {
    primary: { bg: 'var(--c-pos)', fg: '#fff' },
    danger:  { bg: 'var(--c-neg)', fg: '#fff' },
    a1:      { bg: 'var(--c-a1)', fg: '#fff' },
    a2:      { bg: 'var(--c-a2)', fg: '#121212' },
    ghost:   { bg: 'transparent', fg: 'var(--text-strong)', border: 'var(--border)' },
  }[variant]
  const sizeMap = { sm:'px-2 py-1 text-xs', md:'px-3 py-2 text-sm', lg:'px-4 py-2.5 text-sm' }[size]

  return (
    <button type="button"
      className={`inline-flex items-center gap-2 rounded-2xl shadow-sm hover:opacity-95 border ${sizeMap} ${className}`}
      style={{ backgroundColor: map?.bg, color: map?.fg, borderColor: map?.border || 'transparent' }}
      {...props}>
      {Icon && <Icon className="h-5 w-5" />}{children}
    </button>
  )
}
