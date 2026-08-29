/**
 * The seven-day strip above the mobile Day view: simultaneously the week
 * overview the stacked layout lost, and the navigator between days.
 *
 * Each day is a full 44px column (design guide §8.4) showing the weekday
 * initial, the date, and a dot per planned meal — filled when accepted — so the
 * shape of the week is readable without opening every day. Takes plain data:
 * `days` entries already carry their meals, so the strip does no lookups.
 */
export default function CalendarDayStrip({ days, selectedKey, onSelect }) {
  return (
    <div className="flex gap-1">
      {days.map((day) => {
        const active = day.key === selectedKey
        const onSurface = active ? 'var(--text-on-pos, #fff)' : 'var(--text-strong)'
        return (
          <button
            key={day.key}
            type="button"
            aria-pressed={active}
            data-testid="day-strip-day"
            onClick={() => onSelect(day.key)}
            className="flex min-h-11 flex-1 flex-col items-center justify-center rounded-xl px-1 py-1.5 text-xs"
            style={{
              backgroundColor: active ? 'var(--c-pos)' : 'transparent',
              color: onSurface,
              border: `1px solid ${active ? 'var(--c-pos)' : 'var(--border-default)'}`,
            }}
          >
            <span className="opacity-80">{day.short.slice(0, 2)}</span>
            <span className="text-sm font-medium">{day.date.getDate()}</span>
            <span className="mt-0.5 flex h-1.5 items-center gap-0.5">
              {day.meals.map((meal, i) => (
                <span
                  key={i}
                  className="h-1.5 w-1.5 rounded-full"
                  style={{
                    backgroundColor: meal.accepted ? onSurface : 'transparent',
                    border: `1px solid ${active ? onSurface : 'var(--c-a3)'}`,
                  }}
                />
              ))}
            </span>
            {day.today && <span className="sr-only">Today</span>}
          </button>
        )
      })}
    </div>
  )
}
