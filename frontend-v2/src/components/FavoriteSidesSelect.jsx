import React from 'react'
import { PlusIcon, XMarkIcon } from '@heroicons/react/24/outline'
import { Badge } from './Badge'

/**
 * Pick the sides a dish is habitually served with.
 *
 * Selections show as chips; the dropdown offers a search box over the sides not
 * already picked. Follows TagSelector's popover/outside-click pattern but is
 * keyed on `{ id, title }` options rather than plain strings, since sides are
 * persisted by id.
 *
 * `onChange` receives the next array of ids.
 */
export default function FavoriteSidesSelect({
  options = [],
  selected = [],
  onChange,
}) {
  const [open, setOpen] = React.useState(false)
  const [query, setQuery] = React.useState('')
  const ref = React.useRef(null)

  const byId = React.useMemo(
    () => Object.fromEntries(options.map((o) => [o.id, o])),
    [options]
  )

  // Unselected options matching the search. Already-picked sides live in the
  // chips, so offering them again would just be a no-op row.
  const available = React.useMemo(
    () =>
      options.filter(
        (o) =>
          !selected.includes(o.id) &&
          o.title.toLowerCase().includes(query.toLowerCase())
      ),
    [options, selected, query]
  )

  React.useEffect(() => {
    const handleClick = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false)
    }
    if (open) document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [open])

  const add = (id) => {
    onChange([...selected, id])
    setQuery('')
    setOpen(false)
  }

  const remove = (id) => onChange(selected.filter((i) => i !== id))

  return (
    <div className="flex flex-col gap-2" ref={ref}>
      <div className="flex flex-wrap items-center gap-1.5">
        {selected.length === 0 && (
          <span style={{ fontSize: 'var(--text-sm)', color: 'var(--text-muted)' }}>
            No favorite sides yet.
          </span>
        )}
        {selected.map((id) => (
          // Badge renders only its children, so the test id lives on a wrapper.
          <span key={id} data-testid={`favorite-side-chip-${id}`}>
            <Badge tone="caramel">
              {byId[id]?.title || 'Unknown side'}
              <button
                type="button"
                aria-label={`Remove ${byId[id]?.title || 'side'}`}
                onClick={() => remove(id)}
              >
                <XMarkIcon className="h-3 w-3" />
              </button>
            </Badge>
          </span>
        ))}
      </div>

      <div className="relative">
        <button
          type="button"
          onClick={() => setOpen((o) => !o)}
          className="flex items-center gap-1 rounded-xl border px-3 py-1.5 text-sm"
          style={{ borderColor: 'var(--border)', color: 'var(--text-strong)' }}
        >
          <PlusIcon className="h-4 w-4" />
          Add a side
        </button>
        {open && (
          <div
            role="listbox"
            className="absolute top-full left-0 z-10 mt-1 w-64 max-w-full overflow-y-auto rounded-md border bg-white shadow"
            style={{ borderColor: 'var(--border)', maxHeight: '15rem' }}
          >
            <input
              type="text"
              autoFocus
              placeholder="Search side dishes..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="w-full border-b px-2 py-1 text-sm outline-none"
              style={{ borderColor: 'var(--border)' }}
            />
            {options.length === 0 ? (
              <p className="px-2 py-2 text-sm" style={{ color: 'var(--text-muted)' }}>
                No side dishes yet. Create one first.
              </p>
            ) : available.length === 0 ? (
              <p className="px-2 py-2 text-sm" style={{ color: 'var(--text-muted)' }}>
                No match.
              </p>
            ) : (
              available.map((o) => (
                <div
                  key={o.id}
                  role="option"
                  aria-selected={false}
                  className="cursor-pointer px-2 py-1 text-sm hover:bg-gray-100"
                  onClick={() => add(o.id)}
                >
                  {o.title}
                </div>
              ))
            )}
          </div>
        )}
      </div>
    </div>
  )
}
