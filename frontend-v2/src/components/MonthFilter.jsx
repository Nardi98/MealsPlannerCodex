import React from 'react'
import SeasonalitySelect from './SeasonalitySelect'

const MODES = [
  { value: 'any', label: 'At least one month' },
  { value: 'all', label: 'All selected months' },
]

export default function MonthFilter({
  selectedMonths = [],
  onMonthsChange,
  mode = 'any',
  onModeChange,
}) {
  return (
    <div className="flex items-center gap-2">
      <SeasonalitySelect value={selectedMonths} onChange={onMonthsChange} />
      <select
        value={mode}
        onChange={(e) => onModeChange?.(e.target.value)}
        className="rounded-xl border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[color:var(--c-a2)]"
        style={{ borderColor: 'var(--border)', color: 'var(--text-strong)' }}
      >
        {MODES.map((m) => (
          <option key={m.value} value={m.value}>
            {m.label}
          </option>
        ))}
      </select>
    </div>
  )
}

