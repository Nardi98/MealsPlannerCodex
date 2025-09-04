export function Input({ className='', ...props }) {
  return (
    <input {...props}
      className={`rounded-xl border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[color:var(--c-a2)] ${className}`}
      style={{ borderColor: 'var(--border)', color: 'var(--text-strong)' }}/>
  )
}
