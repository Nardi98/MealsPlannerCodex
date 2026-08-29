import React from 'react'
import { XMarkIcon } from '@heroicons/react/24/outline'
import { IconButton } from './IconButton'
import { SCRIM, Z } from '../lib/layers'

/**
 * A panel anchored to the bottom of the viewport.
 *
 * `ModalScrim` centers its child, which is right for a dialog and wrong for a
 * sheet, so this lays out its own wash with `alignItems: flex-end` rather than
 * fighting it -- but takes `SCRIM` and `Z` from the same module so the wash
 * colour and the stacking order stay in one place.
 *
 * Bottom-anchored because a thumb reaches the bottom of a phone and not the
 * top: the controls in here are the ones pressed repeatedly. `footer` is
 * pinned below the scrolling body so a primary action stays put however long
 * the content is.
 */
export default function BottomSheet({ title, onClose, footer, children }) {
  React.useEffect(() => {
    const onKey = (e) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div
      onClick={onClose}
      style={{
        position: 'fixed',
        inset: 0,
        backgroundColor: SCRIM,
        display: 'flex',
        alignItems: 'flex-end',
        zIndex: Z.modal,
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onClick={(e) => e.stopPropagation()}
        className="flex w-full flex-col bg-white"
        style={{
          borderTopLeftRadius: 'var(--radius-lg)',
          borderTopRightRadius: 'var(--radius-lg)',
          maxHeight: '85vh',
          paddingBottom: 'env(safe-area-inset-bottom)',
        }}
      >
        <div className="flex items-center justify-between px-4 pt-2">
          <h3
            style={{
              margin: 0,
              fontSize: 'var(--text-lg)',
              fontWeight: 'var(--weight-semibold)',
              color: 'var(--text-strong)',
            }}
          >
            {title}
          </h3>
          <IconButton Icon={XMarkIcon} label="Close" onClick={onClose} />
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto px-4 pb-2">{children}</div>
        {footer && (
          <div className="border-t px-4 py-3" style={{ borderColor: 'var(--border-default)' }}>
            {footer}
          </div>
        )}
      </div>
    </div>
  )
}
