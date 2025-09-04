import React from 'react'

const MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
const ALL_MONTHS = Array.from({ length: 12 }, (_, i) => i + 1)

export default function SeasonalitySelect({ value = [], onChange }) {
  const [open, setOpen] = React.useState(false)
  const toggle = (m) => {
    onChange(
      value.includes(m) ? value.filter((v) => v !== m) : [...value, m]
    )
  }
  const selectAll = () => onChange(ALL_MONTHS)
  const deselectAll = () => onChange([])
  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="rounded-xl border px-3 py-2 text-sm flex justify-between w-full"
        style={{ borderColor: 'var(--border)', color: 'var(--text-strong)' }}
      >
        {value.length ? `${value.length} month${value.length > 1 ? 's' : ''} selected` : 'Select months'}
      </button>
      {open && (
        <div
          className="absolute z-10 mt-1 max-h-48 overflow-auto rounded-xl border bg-white p-2 text-sm"
          style={{ borderColor: 'var(--border)', color: 'var(--text-strong)' }}
        >
          <div className="flex justify-between mb-2">
            <button type="button" className="px-2 py-1 hover:bg-gray-100 rounded" onClick={selectAll}>
              Select all
            </button>
            <button type="button" className="px-2 py-1 hover:bg-gray-100 rounded" onClick={deselectAll}>
              Deselect all
            </button>
          </div>
          <div className="grid grid-cols-3 gap-2">
            {MONTHS.map((m, i) => (
              <button
                key={m}
                type="button"
                onClick={() => toggle(i + 1)}
                className="flex items-center gap-1"
              >
                <span>{m}</span>
                {value.includes(i + 1) && <span>✓</span>}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

