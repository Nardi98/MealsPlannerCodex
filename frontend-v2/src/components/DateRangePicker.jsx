import React from 'react'
import { DayPicker } from 'react-day-picker'
import { format, parseISO } from 'date-fns'
import { CalendarDaysIcon, XMarkIcon } from '@heroicons/react/24/outline'
import 'react-day-picker/style.css'

const toStr = (d) => format(d, 'yyyy-MM-dd')
const parse = (s) => (s ? parseISO(s) : undefined)

/**
 * A single control that replaces the two start/end date inputs: a trigger
 * reading back the chosen range ("1 Jan – 7 Jan · 7 days") that opens a
 * one-month calendar popover. First click sets the start, second click sets the
 * end (auto-ordered), and a close icon / outside-click / Esc dismisses it.
 *
 * `start`/`end` are `YYYY-MM-DD` strings and `onChange({ start, end })` returns
 * the same shape, matching the existing form/page state.
 */
export default function DateRangePicker({
  start,
  end,
  onChange,
  label,
  placeholder = 'Select dates',
}) {
  const [open, setOpen] = React.useState(false)
  const [anchor, setAnchor] = React.useState(null)
  const ref = React.useRef(null)

  const from = parse(start)
  const to = parse(end)

  React.useEffect(() => {
    if (!open) return undefined
    const onDown = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false)
    }
    const onKey = (e) => {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDown)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  // First click anchors the start; the second click completes the range and
  // auto-orders the two ends so start always precedes end.
  const handleDayPick = (day) => {
    if (!day) return
    if (!anchor) {
      setAnchor(day)
      onChange({ start: toStr(day), end: toStr(day) })
    } else {
      const [a, b] = anchor <= day ? [anchor, day] : [day, anchor]
      setAnchor(null)
      onChange({ start: toStr(a), end: toStr(b) })
    }
  }

  const dayCount = from && to ? Math.round((to - from) / 86400000) + 1 : 0
  const triggerLabel =
    from && to
      ? `${format(from, 'd MMM')} – ${format(to, 'd MMM')} · ${dayCount} ${
          dayCount === 1 ? 'day' : 'days'
        }`
      : placeholder

  return (
    <div className="relative" ref={ref}>
      {label && <span className="mb-1 block text-sm">{label}</span>}
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center gap-2 border px-3 py-2 text-left text-sm focus:outline-none focus:ring-2 focus:ring-[color:var(--c-a2)]"
        style={{
          borderRadius: 'var(--radius-md)',
          borderColor: 'var(--border-default)',
          color: from && to ? 'var(--text-strong)' : 'var(--text-subtle)',
          fontFamily: 'var(--font-body)',
        }}
      >
        <CalendarDaysIcon className="h-4 w-4 shrink-0" aria-hidden="true" />
        <span>{triggerLabel}</span>
      </button>
      {open && (
        <div
          className="absolute z-50 mt-2 border bg-white p-2 shadow-lg"
          style={{
            borderRadius: 'var(--radius-lg)',
            borderColor: 'var(--border-default)',
          }}
        >
          <div className="flex justify-end">
            <button
              type="button"
              aria-label="Close"
              onClick={() => setOpen(false)}
              className="rounded p-1 hover:bg-[color:var(--surface-muted,#f3f4f6)]"
            >
              <XMarkIcon className="h-4 w-4" aria-hidden="true" />
            </button>
          </div>
          <DayPicker
            mode="range"
            weekStartsOn={1}
            defaultMonth={from || new Date()}
            selected={{ from, to }}
            onSelect={(_range, triggerDate) => handleDayPick(triggerDate)}
          />
        </div>
      )}
    </div>
  )
}
