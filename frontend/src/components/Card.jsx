export function Card({ children, className = '' }) {
  return (
    <div
      className={`rounded-2xl border p-4 shadow-sm ${className}`}
      style={{ borderColor: 'var(--border)', backgroundColor: 'var(--c-white)', color: 'var(--text-strong)' }}
    >
      {children}
    </div>
  );
}
