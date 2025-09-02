import React from 'react'

const MONTHS = Array.from({ length: 12 }, (_, i) => i + 1)
const LABELS = ['J', 'F', 'M', 'A', 'M', 'J', 'J', 'A', 'S', 'O', 'N', 'D']

export default function SeasonalityGrid({ months = [] }) {
  return (
    <div className="grid grid-cols-12 gap-x-1 gap-y-0.5">
      {MONTHS.map((m, i) => (
        <div key={m} className="flex flex-col items-center gap-0.5">
          <div
            className="h-2 w-full rounded"
            style={{
              backgroundColor: months.includes(m)
                ? 'var(--c-a1)'
                : 'var(--c-white)',
            }}
          />
          <span className="text-[10px] text-gray-400">{LABELS[i]}</span>
        </div>
      ))}
    </div>
  )
}
