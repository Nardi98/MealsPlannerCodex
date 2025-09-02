import React from 'react'

const MONTHS = Array.from({ length: 12 }, (_, i) => i + 1)

export default function SeasonalityGrid({ months = [] }) {
  return (
    <div className="grid grid-cols-12 gap-1">
      {MONTHS.map((m) => (
        <div
          key={m}
          className="h-2 w-full rounded"
          style={{ backgroundColor: months.includes(m) ? 'var(--c-a1)' : 'var(--text-subtle)' }}
        />
      ))}
    </div>
  )
}
