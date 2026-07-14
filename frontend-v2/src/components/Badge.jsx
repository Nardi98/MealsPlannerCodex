// Tone → CSS color variable. Accepts the legacy short names (a1/a2/a3/pos/neg)
// and the design-system named / category tones.
const TONES = {
  // legacy
  a1: 'var(--c-a1)',
  a2: 'var(--c-a2)',
  a3: 'var(--c-a3)',
  pos: 'var(--c-pos)',
  neg: 'var(--c-neg)',
  // named
  forest: 'var(--c-pos)',
  sage: 'var(--c-a1)',
  gold: 'var(--c-a2)',
  caramel: 'var(--c-a3)',
  danger: 'var(--c-neg)',
  // category
  terracotta: 'var(--cat-terracotta)',
  teal: 'var(--cat-teal)',
  plum: 'var(--cat-plum)',
  berry: 'var(--cat-berry)',
  olive: 'var(--cat-olive)',
  sky: 'var(--cat-sky)',
}

export function Badge({ tone = 'caramel', children }) {
  const fg = TONES[tone] || TONES.caramel
  return (
    <span className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs"
          style={{ backgroundColor: `color-mix(in srgb, ${fg} 16%, transparent)`, color: fg }}>
      {children}
    </span>
  )
}
