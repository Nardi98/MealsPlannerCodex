import React from 'react'
import { BarsArrowDownIcon, BarsArrowUpIcon } from '@heroicons/react/24/outline'
import { IconButton } from './IconButton'
import { Input } from './Input'
import { SORT_OPTIONS, defaultDirectionFor } from '../utils/sortRecipes'

/**
 * Sort picker for the recipe grid: a key select plus an arrow that flips the
 * direction. Picking a key reports the direction that key reads best in, so
 * the common case ("show me my best recipes") needs no second click.
 */
export default function RecipeSort({ sortKey, direction, onChange, onDirectionChange }) {
  const next = direction === 'asc' ? 'desc' : 'asc'

  return (
    <div className="flex items-center gap-1">
      <Input
        as="select"
        aria-label="Sort recipes"
        value={sortKey}
        onChange={(e) => onChange?.(e.target.value, defaultDirectionFor(e.target.value))}
      >
        {SORT_OPTIONS.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </Input>
      <IconButton
        Icon={next === 'desc' ? BarsArrowDownIcon : BarsArrowUpIcon}
        label={next === 'desc' ? 'Sort descending' : 'Sort ascending'}
        // Nothing to reverse while the list is in the server's own order.
        disabled={sortKey === 'default'}
        onClick={() => onDirectionChange?.(next)}
      />
    </div>
  )
}
