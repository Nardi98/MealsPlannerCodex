/** "4 Sep 2026" in whoever's locale is reading, or nothing for a missing date. */
export const shownDate = (value) => {
  if (!value) return ''
  const parsed = new Date(value)
  return Number.isNaN(parsed.getTime())
    ? String(value)
    : parsed.toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' })
}
