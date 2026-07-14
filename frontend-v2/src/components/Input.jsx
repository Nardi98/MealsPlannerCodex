export function Input({ className='', style={}, ...props }) {
  return (
    <input {...props}
      className={`border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[color:var(--c-a2)] ${className}`}
      style={{
        borderRadius: 'var(--radius-md)',
        borderColor: 'var(--border-default)',
        color: 'var(--text-strong)',
        fontFamily: 'var(--font-body)',
        ...style,
      }}/>
  )
}
