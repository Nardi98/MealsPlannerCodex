/**
 * Day / Week switch for the mobile calendar.
 *
 * Plain buttons with `aria-pressed` rather than a tablist: `SegmentedControl`
 * is the project's tablist primitive and implements roving focus and arrow
 * keys, and a `role="tablist"` that ignores arrow keys is a worse promise than
 * no tablist at all. This is a two-state switch, not a tab strip.
 */
export default function CalendarViewToggle({ value, onChange, options }) {
  return (
    <div
      className="flex gap-1 p-1"
      style={{ border: '1px solid var(--border-default)', borderRadius: 'var(--radius-md)' }}
    >
      {options.map(([option, label]) => {
        const active = value === option
        return (
          <button
            key={option}
            type="button"
            aria-pressed={active}
            onClick={() => onChange(option)}
            className="min-h-11 flex-1 text-sm font-medium"
            style={{
              backgroundColor: active ? 'var(--c-pos)' : 'transparent',
              color: active ? 'var(--text-on-pos, #fff)' : 'var(--text-strong)',
              borderRadius: 'var(--radius-sm)',
            }}
          >
            {label}
          </button>
        )
      })}
    </div>
  )
}
