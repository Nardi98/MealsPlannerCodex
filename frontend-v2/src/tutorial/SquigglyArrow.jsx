import React from 'react'

// A hand-drawn-looking arrow, pointing from the tutorial bubble at the thing it
// is talking about. Drawn rather than imported so it inherits `currentColor`
// and needs no asset pipeline.
//
// The path is authored pointing *up* (tip at the top). The other three
// directions are the same path rotated, which keeps the wobble consistent
// instead of needing four hand-drawn variants that never quite match.
const ROTATION = { up: 0, right: 90, down: 180, left: 270 }

const SIZE = 46

export function SquigglyArrow({ direction = 'up' }) {
  const rotate = ROTATION[direction] ?? 0
  return (
    <svg
      data-testid="tour-arrow"
      width={SIZE}
      height={SIZE}
      viewBox="0 0 48 48"
      fill="none"
      aria-hidden="true"
      focusable="false"
      style={{ transform: `rotate(${rotate}deg)`, color: 'var(--c-a2)' }}
    >
      {/* the wobbling tail, sweeping up from the bubble */}
      <path
        d="M38 43C30 37 35 28 26 24 17 20 24 14 24 7"
        stroke="currentColor"
        strokeWidth="2.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      {/* the head, at the tail's tip */}
      <path
        d="M17.5 13.5 24 6l6.5 7.5"
        stroke="currentColor"
        strokeWidth="2.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}
