import { XMarkIcon } from '@heroicons/react/24/outline'

/**
 * The filters currently narrowing the grid, each removable, plus a clear-all.
 *
 * Without this the only cue that a filter is on is the grid being short -- and
 * once the popover or sheet is closed there is nothing on screen saying why.
 * Renders nothing when no filter is active.
 *
 * `filters` is `[{ value, onRemove }]`.
 */
export default function ActiveFilterChips({ filters, onClearAll }) {
  if (filters.length === 0) return null

  return (
    <div className="flex flex-wrap items-center gap-2">
      {filters.map(({ value, onRemove }) => (
        <button
          key={value}
          type="button"
          aria-label={`Remove filter ${value}`}
          onClick={onRemove}
          className="inline-flex min-h-9 items-center gap-1 rounded-full border px-3 text-xs"
          style={{ borderColor: 'var(--border-default)', color: 'var(--text-strong)' }}
        >
          {value}
          <XMarkIcon className="h-3.5 w-3.5" aria-hidden="true" />
        </button>
      ))}
      <button
        type="button"
        aria-label="Clear all filters"
        onClick={onClearAll}
        className="min-h-9 px-2 text-xs underline"
        style={{ color: 'var(--c-neg)' }}
      >
        Clear all
      </button>
    </div>
  )
}
