import React from 'react'
import { ChevronDownIcon } from '@heroicons/react/24/outline'
import { Input } from './Input'

/**
 * The three recipe filter groups -- course, tags, ingredients -- as collapsible
 * sets of toggle chips.
 *
 * Shared by the mobile bottom sheet and the desktop popover so the two
 * surfaces cannot drift apart. Chips rather than the native checkboxes that
 * were here before: a 13px checkbox is a third of the 44px target design guide
 * §8.4 requires, and three of them nested their own scroll areas inside a
 * popover inside the page scroll.
 *
 * `ToggleChip` is deliberately not reused: it is `px-2.5 py-1 text-xs` with no
 * minimum height, sized for dense inline rows, and raising it to 44px would
 * change every other place it appears.
 *
 * `groups` is `[{ label, options, selected, onSelect, searchable }]`.
 */

function Chip({ option, active, onSelect }) {
  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={() => onSelect(option)}
      className="min-h-11 rounded-full border px-4 text-sm"
      style={{
        borderColor: active ? 'var(--c-a2)' : 'var(--border-default)',
        backgroundColor: active
          ? 'color-mix(in srgb, var(--c-a2) 14%, transparent)'
          : 'transparent',
        color: active ? 'var(--c-a2)' : 'var(--text-strong)',
      }}
    >
      {option}
    </button>
  )
}

/**
 * The options of one open group.
 *
 * A component of its own so that `query` unmounts with the group: collapsing
 * and reopening starts clean without an effect having to notice.
 *
 * A `searchable` group lists nothing until something is typed. The ingredient
 * group is the whole of an account's catalogue -- rendering it as 44px chips
 * meant hundreds of them in one sheet, which is the problem the chips were
 * supposed to solve rather than a smaller version of it. Selected options are
 * the exception and always show: a filter you have switched on has to stay
 * reachable, or turning it off means guessing the name of what you picked.
 */
function FilterOptions({ label, options, selected, onSelect, searchable }) {
  const [query, setQuery] = React.useState('')

  const matches = React.useMemo(() => {
    if (!searchable) return options
    const q = query.trim().toLowerCase()
    if (!q) return []
    return options.filter((o) => o.toLowerCase().includes(q))
  }, [options, query, searchable])

  // Selected first and only once, so a selected match is not listed twice.
  const listed = searchable
    ? [...selected, ...matches.filter((o) => !selected.includes(o))]
    : matches

  return (
    <div className="flex flex-col gap-2 pb-2">
      {searchable && (
        <Input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={`Search ${label}…`}
          aria-label={`Search ${label}`}
        />
      )}
      {listed.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {listed.map((option) => (
            <Chip
              key={option}
              option={option}
              active={selected.includes(option)}
              onSelect={onSelect}
            />
          ))}
        </div>
      )}
    </div>
  )
}

export default function RecipeFilters({ groups }) {
  const [openLabel, setOpenLabel] = React.useState(null)

  return (
    <div className="flex flex-col gap-2">
      {groups.map(({ label, options, selected, onSelect, searchable }) => {
        const open = openLabel === label
        return (
          <div key={label}>
            <button
              type="button"
              aria-expanded={open}
              onClick={() => setOpenLabel(open ? null : label)}
              className="flex min-h-11 w-full items-center gap-2 text-sm font-medium"
              style={{ color: 'var(--text-strong)' }}
            >
              {label}
              {selected.length > 0 && (
                <span className="ml-auto text-xs" style={{ color: 'var(--text-subtle)' }}>
                  {selected.length}
                </span>
              )}
              <ChevronDownIcon
                className={`h-4 w-4 transition-transform${selected.length > 0 ? '' : ' ml-auto'}`}
                style={{ transform: open ? 'rotate(180deg)' : undefined }}
              />
            </button>
            {open && (
              <FilterOptions
                label={label}
                options={options}
                selected={selected}
                onSelect={onSelect}
                searchable={searchable}
              />
            )}
          </div>
        )
      })}
    </div>
  )
}
