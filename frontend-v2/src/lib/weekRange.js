/**
 * Label for the week a calendar is showing, e.g. "1–7 Jan" or "29 Jan – 4 Feb".
 *
 * The calendar previously offered no date context beyond a `D/M` per column,
 * which disappeared entirely in the mobile layout.
 */
export function formatWeekRange(days) {
  if (!days || days.length === 0) return ''
  const first = days[0]
  const last = days[days.length - 1]
  const dayMonth = (d) =>
    d.toLocaleDateString(undefined, { day: 'numeric', month: 'short' })
  if (first.getMonth() === last.getMonth()) {
    return `${first.getDate()}–${dayMonth(last)}`
  }
  return `${dayMonth(first)} – ${dayMonth(last)}`
}
