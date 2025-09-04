import React from 'react'

export default function MonthGrid({ baseDate, startDate, endDate }) {
  const monthStart = new Date(baseDate.getFullYear(), baseDate.getMonth(), 1)
  const monthEnd = new Date(baseDate.getFullYear(), baseDate.getMonth() + 1, 0)

  const gridStart = new Date(monthStart)
  const startDay = gridStart.getDay()
  const startDiff = startDay === 0 ? -6 : 1 - startDay
  gridStart.setDate(gridStart.getDate() + startDiff)

  const gridEnd = new Date(monthEnd)
  const endDay = gridEnd.getDay()
  const endDiff = endDay === 0 ? 0 : 7 - endDay
  gridEnd.setDate(gridEnd.getDate() + endDiff)

  const days = []
  for (let d = new Date(gridStart); d <= gridEnd; d.setDate(d.getDate() + 1)) {
    const current = new Date(d)
    const inCurrentMonth = current.getMonth() === baseDate.getMonth()
    const inRange =
      startDate && endDate && current >= startDate && current <= endDate
    days.push(
      <div
        key={current.toISOString()}
        className="h-8 flex flex-col items-center justify-center text-sm"
      >
        <div
          className={`w-7 h-7 flex items-center justify-center rounded-full ${
            inCurrentMonth
              ? 'text-[color:var(--text-strong)]'
              : 'text-[color:var(--text-subtle)] opacity-60'
          }`}
        >
          {inCurrentMonth ? current.getDate() : ''}
        </div>
        <div
          className="h-1 w-6 mt-0.5 rounded-full"
          style={{ backgroundColor: inRange ? 'var(--c-a1)' : 'transparent' }}
        />
      </div>
    )
  }

  const label = monthStart.toLocaleDateString(undefined, {
    month: 'long',
    year: 'numeric',
  })

  return (
    <div className="flex flex-col items-center">
      <div className="grid grid-cols-7 gap-x-1 gap-y-2">{days}</div>
      <div className="mt-2 text-sm font-medium text-[color:var(--text-strong)]">
        {label}
      </div>
    </div>
  )
}

