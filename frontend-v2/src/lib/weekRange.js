import { format } from 'date-fns'

/**
 * Label for the week a calendar is showing, e.g. "1–7 Jan" or "29 Jan – 4 Feb".
 *
 * The calendar previously offered no date context beyond a `D/M` per column,
 * which disappeared entirely in the mobile layout. Uses `date-fns` so the
 * string matches `DateRangePicker`'s on the same page rather than drifting
 * from it.
 */
export function formatWeekRange(days) {
  if (!days || days.length === 0) return ''
  const first = days[0]
  const last = days[days.length - 1]
  if (first.getMonth() === last.getMonth()) {
    return `${format(first, 'd')}–${format(last, 'd MMM')}`
  }
  return `${format(first, 'd MMM')} – ${format(last, 'd MMM')}`
}
