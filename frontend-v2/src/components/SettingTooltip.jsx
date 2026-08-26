import React from 'react'
import { createPortal } from 'react-dom'
import { Card } from './Card'
import { placeBubble, maxBubbleHeight } from '../lib/placement'

// Long enough that it never fires while the pointer is only crossing the form on
// its way somewhere else, short enough to feel like an answer to a question.
export const HOVER_DELAY_MS = 2000

const WIDTH = 300
// No arrow to make room for — just enough clearance that the bubble reads as
// sitting outside the control rather than on it.
const GAP = 10

const TITLE_STYLE = {
  margin: '0 0 4px',
  fontSize: 13,
  fontWeight: 'var(--weight-semibold)',
  color: 'var(--text-strong)',
}
const BODY_STYLE = { margin: 0, fontSize: 12, lineHeight: 1.5, color: 'var(--text-muted)' }
const LIST_STYLE = { margin: '10px 0 0', padding: 0, listStyle: 'none' }

/**
 * Explains the setting it wraps. Hover it for a couple of seconds — or focus it
 * from the keyboard, or long-press it on a touch screen — and a bubble appears
 * with what the setting does and what each preset means; it goes away the moment
 * the pointer leaves.
 *
 * The bubble is anchored on the *whole* labelled control and placed outside its
 * box, so it can never sit on top of the slider or segmented bar the user is
 * about to drag. It is also `pointer-events: none`, so even a mis-measurement
 * cannot swallow that drag.
 */
export default function SettingTooltip({ title, body, presets, className, children }) {
  const [open, setOpen] = React.useState(false)
  // Anchor and bubble geometry, measured together once the bubble exists — see
  // the layout effect below.
  const [box, setBox] = React.useState(null)
  const anchor = React.useRef(null)
  const bubble = React.useRef(null)
  const timer = React.useRef(null)
  const id = React.useId()

  const cancel = () => {
    clearTimeout(timer.current)
    timer.current = null
  }

  const hide = React.useCallback(() => {
    clearTimeout(timer.current)
    timer.current = null
    setOpen(false)
  }, [])

  const openAfterDelay = () => {
    cancel()
    timer.current = setTimeout(() => setOpen(true), HOVER_DELAY_MS)
  }

  React.useEffect(() => cancel, [])

  // While it is up, anything that moves the page out from under the bubble — a
  // scroll, a resize, a press anywhere — takes it down again, as does Escape:
  // re-placing it mid-scroll would be more distracting than losing it, and a
  // press means the user is about to drag the control it is explaining.
  React.useEffect(() => {
    if (!open) return undefined
    const onKey = (e) => e.key === 'Escape' && hide()
    document.addEventListener('keydown', onKey)
    document.addEventListener('pointerdown', hide)
    window.addEventListener('scroll', hide, true)
    window.addEventListener('resize', hide)
    return () => {
      document.removeEventListener('keydown', onKey)
      document.removeEventListener('pointerdown', hide)
      window.removeEventListener('scroll', hide, true)
      window.removeEventListener('resize', hide)
    }
  }, [open, hide])

  // Both rects in one read, before paint: the copy varies per setting, and an
  // estimated height that reads low is how a bubble ends up overlapping the very
  // control it explains. Measuring here rather than during render also keeps the
  // reflow out of the eight other wrappers' renders.
  React.useLayoutEffect(() => {
    if (!open) return
    const rect = anchor.current.getBoundingClientRect()
    const size = bubble.current.getBoundingClientRect()
    setBox({ rect, size: { width: size.width, height: size.height } })
  }, [open])

  const viewport = open ? { width: window.innerWidth, height: window.innerHeight } : null
  const at = open ? placeBubble(box?.rect, 'top', viewport, box?.size, GAP) : null

  return (
    <div
      ref={anchor}
      data-setting-tooltip=""
      className={className}
      aria-describedby={open ? id : undefined}
      onPointerEnter={openAfterDelay}
      onPointerLeave={hide}
      // On touch, `pointerdown` fires first and takes the bubble down (see the
      // effect above); this re-arms it as a long press.
      onTouchStart={openAfterDelay}
      onTouchEnd={cancel}
      onTouchCancel={hide}
      onFocusCapture={() => setOpen(true)}
      onBlurCapture={hide}
    >
      {children}
      {open &&
        createPortal(
          <Card
            ref={bubble}
            role="tooltip"
            id={id}
            style={{
              position: 'fixed',
              top: at.top,
              left: at.left,
              zIndex: 90,
              // Never a drag target: the control underneath always wins.
              pointerEvents: 'none',
              width: WIDTH,
              boxSizing: 'border-box',
              maxHeight: maxBubbleHeight(viewport),
              overflowY: 'auto',
              boxShadow: 'var(--shadow-lg)',
              padding: 14,
              fontFamily: 'var(--font-display)',
            }}
          >
            <h4 style={TITLE_STYLE}>{title}</h4>
            <p style={BODY_STYLE}>{body}</p>
            {presets?.length > 0 && (
              <ul style={LIST_STYLE}>
                {presets.map((preset) => (
                  <li key={preset.label} style={BODY_STYLE}>
                    <strong style={{ color: 'var(--text-strong)' }}>{preset.label}</strong>
                    {' — '}
                    {preset.text}
                  </li>
                ))}
              </ul>
            )}
          </Card>,
          document.body,
        )}
    </div>
  )
}
