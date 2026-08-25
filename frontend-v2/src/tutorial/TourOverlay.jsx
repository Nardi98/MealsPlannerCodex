import React from 'react'
import { createPortal } from 'react-dom'
import { SCRIM } from '../components/Modal'

// Above Modal (60) and ProfileMenu (50): the tutorial has to be able to talk
// about a page that already has a dialog open.
const Z = 100

// The dimmed backdrop with a bright hole cut around the step's target.
//
// Four rectangles rather than an SVG mask: the panels are ordinary elements, so
// they block clicks on the dimmed page for free. A fifth, transparent element
// covers the bright cutout for the same reason — while the tour is running the
// user walks it with the tour's buttons, not by poking the page underneath.
function Panel({ style }) {
  return <div style={{ position: 'fixed', background: SCRIM, ...style }} />
}

export function TourOverlay({ rect, children }) {
  // A portal on the body: the sidebar wrapper in App.jsx is `overflow-hidden`
  // and would clip a bubble anchored to anything inside it.
  return createPortal(
    <div data-testid="tour-overlay" style={{ position: 'fixed', inset: 0, zIndex: Z }}>
      {rect ? (
        <>
          <Panel style={{ top: 0, left: 0, right: 0, height: Math.max(0, rect.top) }} />
          <Panel style={{ top: rect.top + rect.height, left: 0, right: 0, bottom: 0 }} />
          <Panel style={{ top: rect.top, left: 0, width: Math.max(0, rect.left), height: rect.height }} />
          <Panel style={{ top: rect.top, left: rect.left + rect.width, right: 0, height: rect.height }} />
          {/* the highlight ring around the bright cutout */}
          <div
            style={{
              position: 'fixed',
              top: rect.top - 4,
              left: rect.left - 4,
              width: rect.width + 8,
              height: rect.height + 8,
              border: '2px solid var(--c-a2)',
              borderRadius: 'var(--radius-md)',
              pointerEvents: 'none',
            }}
          />
          {/* swallows clicks on the cutout: look, don't touch */}
          <div
            data-testid="tour-cutout-shield"
            style={{
              position: 'fixed',
              top: rect.top,
              left: rect.left,
              width: rect.width,
              height: rect.height,
            }}
          />
        </>
      ) : (
        <Panel style={{ inset: 0 }} />
      )}
      {children}
    </div>,
    document.body,
  )
}
