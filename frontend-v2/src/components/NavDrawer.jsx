import React from 'react'
import { SCRIM, Z } from '../lib/layers'
import Sidebar from './Sidebar'

// The mobile counterpart of the desktop sidebar column: a scrim plus a
// left-anchored panel holding the same `Sidebar`, so the two can never drift
// apart. Rendered only below `md` — see `useIsMobile`.
export default function NavDrawer({ open, onClose }) {
  React.useEffect(() => {
    if (!open) return undefined
    const onKeyDown = (e) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [open, onClose])

  if (!open) return null

  return (
    <div
      data-testid="nav-drawer-scrim"
      onClick={onClose}
      style={{
        position: 'fixed',
        inset: 0,
        backgroundColor: SCRIM,
        zIndex: Z.drawer,
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Main navigation"
        onClick={(e) => e.stopPropagation()}
        className="flex flex-col gap-3"
        style={{
          position: 'absolute',
          top: 0,
          left: 0,
          bottom: 0,
          padding: 12,
          overflowY: 'auto',
          boxSizing: 'border-box',
        }}
      >
        <Sidebar onNavigate={onClose} />
      </div>
    </div>
  )
}
