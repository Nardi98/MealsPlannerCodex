import React from 'react'

/**
 * A pill-shaped toggle button. Used for category selection, section filtering
 * and the recipe filter groups.
 *
 * Two sizes, because the accent styling below is the same recipe either way and
 * having two components own it meant a token change had to be found twice:
 *
 * - `sm` (default) is a dense inline row — secondary text, no minimum height.
 * - `lg` is a 44px tap target per design guide §8.4, with primary text. It is
 *   what a filter chip is: the chips *are* the control, not a label beside one.
 */
export default function ToggleChip({ active, onClick, label, size = 'sm', children }) {
  const large = size === 'lg'

  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      aria-label={label}
      className={`rounded-full border transition-colors ${
        large ? 'min-h-11 px-4 text-sm' : 'px-2.5 py-1 text-xs'
      }`}
      style={{
        borderColor: active ? 'var(--c-a2)' : 'var(--border)',
        backgroundColor: active
          ? 'color-mix(in srgb, var(--c-a2) 14%, transparent)'
          : 'transparent',
        color: active ? 'var(--c-a2)' : `var(${large ? '--text-strong' : '--text-subtle'})`,
      }}
    >
      {children}
    </button>
  )
}
