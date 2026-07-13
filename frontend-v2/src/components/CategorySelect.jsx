import React from 'react'
import ToggleChip from './ToggleChip'
import { CATEGORIES } from '../constants/categories'

/**
 * Multi-select control for ingredient categories rendered as toggle chips.
 *
 * `value` is an array of selected category strings; `onChange` receives the
 * next array when a chip is toggled.
 */
export default function CategorySelect({ value = [], onChange }) {
  const selected = new Set(value)

  const toggle = (category) => {
    const next = new Set(selected)
    if (next.has(category)) {
      next.delete(category)
    } else {
      next.add(category)
    }
    onChange?.(CATEGORIES.filter((c) => next.has(c)))
  }

  return (
    <div className="flex flex-wrap gap-1.5">
      {CATEGORIES.map((category) => (
        <ToggleChip
          key={category}
          active={selected.has(category)}
          onClick={() => toggle(category)}
        >
          {category}
        </ToggleChip>
      ))}
    </div>
  )
}
