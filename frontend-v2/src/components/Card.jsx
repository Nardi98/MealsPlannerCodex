export function Card({ children, className='' }) {
  return (
    <div className={`rounded-2xl border bg-white p-4 shadow-sm ${className}`} style={{ borderColor: 'var(--border)' }}>
      {children}
    </div>
  )
}
