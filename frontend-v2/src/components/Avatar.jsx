// Palette drawn from the design tokens so avatars sit inside the app's colour
// language rather than introducing arbitrary hues.
const COLORS = [
  'var(--cat-berry)',
  'var(--cat-olive)',
  'var(--cat-teal)',
  'var(--cat-plum)',
  'var(--c-a1)',
  'var(--c-a2)',
  'var(--c-pos)',
]

function initials(name, email) {
  const source = (name || '').trim()
  if (source) {
    const parts = source.split(/\s+/)
    if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase()
    return parts[0][0].toUpperCase()
  }
  if (email && email.trim()) return email.trim()[0].toUpperCase()
  return '?'
}

function colorFor(seed) {
  let hash = 0
  for (let i = 0; i < seed.length; i += 1) {
    hash = (hash * 31 + seed.charCodeAt(i)) | 0
  }
  return COLORS[Math.abs(hash) % COLORS.length]
}

export default function Avatar({ name, email, size = 34, className = '', style = {}, ...props }) {
  const text = initials(name, email)
  const background = colorFor(name || email || '')
  return (
    <div
      className={`inline-flex items-center justify-center ${className}`}
      style={{
        width: size,
        height: size,
        borderRadius: '50%',
        background,
        color: '#fff',
        fontFamily: 'var(--font-display)',
        fontWeight: 'var(--weight-medium)',
        fontSize: Math.round(size * 0.4),
        userSelect: 'none',
        ...style,
      }}
      {...props}
    >
      {text}
    </div>
  )
}
