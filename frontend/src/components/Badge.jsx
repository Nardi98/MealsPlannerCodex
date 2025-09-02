export function Badge({ tone = 'a3', children }) {
  const fg = `var(--c-${tone})`;
  return (
    <span
      className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs"
      style={{ backgroundColor: `color-mix(in srgb, ${fg} 14%, transparent)`, color: fg }}
    >
      {children}
    </span>
  );
}
