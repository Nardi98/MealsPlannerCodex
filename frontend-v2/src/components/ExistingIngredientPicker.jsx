import React from 'react'
import { Input } from './'

// Pick an existing ingredient to reuse. Rather than a raw select over the whole
// database, it surfaces the similar-name suggestions first and offers a
// type-to-search fallback over the full list for when the suggestions miss.
export default function ExistingIngredientPicker({
  value,
  options = [],
  suggestions = [],
  onChange,
}) {
  const [query, setQuery] = React.useState('')

  const selected = options.find((o) => o.id === value)
  const results = query.trim()
    ? options.filter((o) => o.name.toLowerCase().includes(query.toLowerCase()))
    : []

  const optionButton = (opt) => {
    const isSelected = opt.id === value
    return (
      <button
        key={opt.id}
        type="button"
        aria-pressed={isSelected}
        onClick={() => onChange?.(opt.id)}
        className={`block w-full text-left px-2 py-1 text-sm rounded ${
          isSelected ? 'font-medium' : 'hover:bg-gray-100'
        }`}
        style={
          isSelected
            ? {
                color: 'var(--c-a1)',
                background: 'color-mix(in srgb, var(--c-a1) 12%, transparent)',
              }
            : { color: 'var(--text-strong)' }
        }
      >
        {opt.name}
        {opt.unit ? (
          <span style={{ color: 'var(--text-muted)' }}> · {opt.unit}</span>
        ) : null}
      </button>
    )
  }

  return (
    <div className="space-y-2">
      {selected && (
        <div className="text-xs" style={{ color: 'var(--text-muted)' }}>
          Selected: {selected.name}
        </div>
      )}

      {suggestions.length > 0 && (
        <div className="space-y-1">
          <div className="text-xs font-medium" style={{ color: 'var(--text-muted)' }}>
            Suggested
          </div>
          {suggestions.map(optionButton)}
        </div>
      )}

      <Input
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Search ingredients…"
      />
      {results.length > 0 && (
        <div
          className="max-h-40 overflow-auto rounded-xl border"
          style={{ borderColor: 'var(--border)' }}
        >
          {results.map(optionButton)}
        </div>
      )}
    </div>
  )
}
