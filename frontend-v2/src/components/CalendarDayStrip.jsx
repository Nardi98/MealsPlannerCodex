/**
 * The seven-day strip above the mobile Day view: simultaneously the week
 * overview the stacked layout lost, and the navigator between days.
 *
 * Each day is a full 44px column (design guide §8.4) showing the weekday
 * initial, the date, and a dot per planned meal — filled when accepted — so the
 * shape of the week is readable without opening every day.
 */
export default function CalendarDayStrip({ days, selectedKey, onSelect, mealsFor }) {
  return (
    <div className="flex gap-1" role="tablist" aria-label="Days of the week">
      {days.map((day) => {
        const active = day.key === selectedKey
        const meals = mealsFor(day.date)
        return (
          <button
            key={day.key}
            type="button"
            role="tab"
            aria-selected={active}
            data-testid="day-strip-day"
            onClick={() => onSelect(day.key)}
            className="flex min-h-11 flex-1 flex-col items-center justify-center rounded-xl px-1 py-1.5 text-xs"
            style={{
              backgroundColor: active ? 'var(--c-pos)' : 'transparent',
              color: active ? '#fff' : 'var(--text-strong)',
              border: `1px solid ${active ? 'var(--c-pos)' : 'var(--border-default)'}`,
            }}
          >
            <span className="opacity-80">{day.short.slice(0, 2)}</span>
            <span className="text-sm font-medium">{day.date.getDate()}</span>
            <span className="mt-0.5 flex h-1.5 items-center gap-0.5">
              {meals.map((meal, i) => (
                <span
                  key={i}
                  className="h-1.5 w-1.5 rounded-full"
                  style={{
                    backgroundColor: meal.accepted
                      ? (active ? '#fff' : 'var(--c-pos)')
                      : 'transparent',
                    border: `1px solid ${active ? '#fff' : 'var(--c-a3)'}`,
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
