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
  ...rest
}) {
  return (
    <div className="flex items-center gap-2" {...rest}>
      <SeasonalitySelect value={selectedMonths} onChange={onMonthsChange} />
      <select
        value={mode}
        onChange={(e) => onModeChange?.(e.target.value)}
        className="rounded-xl border px-3 py-2 text-sm"
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

