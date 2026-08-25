import React from 'react'
import { Card } from '../components/Card'
import { Button } from '../components/Button'
import { SquigglyArrow } from './SquigglyArrow'
import { BUBBLE_WIDTH } from './placement'

// Where the arrow hangs, by the direction it points — the side the target is on.
const ARROW_OFFSET = {
  up: { top: -44, left: 24 },
  down: { bottom: -44, left: 24 },
  left: { left: -44, top: 18 },
  right: { right: -44, top: 18 },
}

// Back and Skip are link-like, not buttons with a surface: `ghost` would give
// them a border and a shadow they should not have.
function LinkButton({ onClick, underline, children }) {
  return (
    <button
      type="button"
      onClick={onClick}
      style={{
        background: 'none',
        border: 'none',
        padding: 0,
        cursor: 'pointer',
        fontSize: 12,
        color: 'var(--text-subtle)',
        textDecoration: underline ? 'underline' : 'none',
      }}
    >
      {children}
    </button>
  )
}

// The tutorial's text box: what this part of the page is for, how far through
// the page's tour you are, and the two ways out.
//
// `arrow` is the direction the arrow points — or null when there is no target
// to point at, in which case the bubble sits in the middle of the screen and
// simply explains itself.
export const TourBubble = React.forwardRef(function TourBubble(
  { title, body, index, total, isLast, arrow, maxHeight, onNext, onBack, onSkip, style },
  ref,
) {
  return (
    <Card
      ref={ref}
      role="dialog"
      aria-modal="true"
      aria-label={title}
      style={{
        position: 'absolute',
        width: BUBBLE_WIDTH,
        boxSizing: 'border-box',
        // A step whose copy runs long scrolls inside the bubble rather than
        // growing past the bottom of the window. The budget comes from the
        // placement module so the bubble is sized and positioned by one rule.
        maxHeight,
        overflowY: 'auto',
        boxShadow: 'var(--shadow-lg)',
        padding: 18,
        fontFamily: 'var(--font-display)',
        ...style,
      }}
    >
      {arrow && (
        <div style={{ position: 'absolute', pointerEvents: 'none', ...ARROW_OFFSET[arrow] }}>
          <SquigglyArrow direction={arrow} />
        </div>
      )}

      <h3
        style={{
          margin: '0 0 6px',
          fontSize: 'var(--text-base, 15px)',
          fontWeight: 'var(--weight-semibold)',
          color: 'var(--text-strong)',
        }}
      >
        {title}
      </h3>
      <p style={{ margin: 0, fontSize: 13, lineHeight: 1.5, color: 'var(--text-muted)' }}>{body}</p>

      <div className="flex items-center justify-between" style={{ marginTop: 16, gap: 12 }}>
        <div className="flex items-center gap-2">
          {index > 0 && <LinkButton onClick={onBack}>‹ Back</LinkButton>}
        </div>

        <div className="flex items-center gap-1.5" aria-label={`Step ${index + 1} of ${total}`}>
          {Array.from({ length: total }, (_, i) => (
            <span
              key={i}
              data-testid="tour-dot"
              data-current={String(i === index)}
              style={{
                width: i === index ? 9 : 6,
                height: i === index ? 9 : 6,
                borderRadius: '50%',
                background: i === index ? 'var(--c-pos)' : 'var(--border)',
                display: 'inline-block',
              }}
            />
          ))}
        </div>
      </div>

      <div className="flex items-center justify-between" style={{ marginTop: 14, gap: 12 }}>
        <LinkButton onClick={onSkip} underline>
          Skip tutorial
        </LinkButton>
        <Button variant="primary" onClick={onNext}>
          {isLast ? 'Done' : 'Next'}
        </Button>
      </div>
    </Card>
  )
})
