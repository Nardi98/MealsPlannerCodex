import React from 'react'

const MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']

export default function SeasonalitySelect({ value = [], onChange }) {
  const [open, setOpen] = React.useState(false)
  const toggle = (m) => {
    onChange(
      value.includes(m) ? value.filter((v) => v !== m) : [...value, m]
    )
  }
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
          className="absolute z-10 mt-1 max-h-48 overflow-auto rounded-xl border bg-white p-2 grid grid-cols-3 gap-2 text-sm"
          style={{ borderColor: 'var(--border)', color: 'var(--text-strong)' }}
        >
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
      )}
    </div>
  )
}

