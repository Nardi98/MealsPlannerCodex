import React from 'react'
import { ChevronDownIcon } from '@heroicons/react/24/outline'

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
 * `groups` is `[{ label, options, selected, onSelect }]`.
 */
export default function RecipeFilters({ groups }) {
  const [openLabel, setOpenLabel] = React.useState(null)

  return (
    <div className="flex flex-col gap-2">
      {groups.map(({ label, options, selected, onSelect }) => {
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
              <div className="flex flex-wrap gap-2 pb-2">
                {options.map((option) => {
                  const active = selected.includes(option)
                  return (
                    <button
                      key={option}
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
                })}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}
