export function isInSeason(months = [], selected = []) {
  if (selected.length === 0) return true
  return months.some((m) => selected.includes(m))
}

export function matchesAll(months = [], selected = []) {
  if (selected.length === 0) return true
  return selected.every((m) => months.includes(m))
}
