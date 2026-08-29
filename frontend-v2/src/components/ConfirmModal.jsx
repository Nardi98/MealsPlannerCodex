import React from 'react'
import { ModalScrim } from './Modal'
import { Card } from './Card'
import { Button } from './Button'
import { Z } from '../lib/layers'

/**
 * A yes/no gate in front of an action that cannot be undone.
 *
 * Rendered at `Z.nested` because it is always raised from inside another
 * dialog -- the recipe detail modal -- and would otherwise sit beneath it.
 * Cancel is the safe default and comes first in the tab order; the confirm
 * button carries the caller's verb ("Delete recipe") rather than a bare "OK",
 * so the button says what it will do without the message having to be read,
 * and is distinguishable by accessible name from the control that opened it.
 */
export default function ConfirmModal({
  title,
  message,
  confirmLabel,
  onConfirm,
  onCancel,
}) {
  React.useEffect(() => {
    const onKey = (e) => {
      if (e.key === 'Escape') onCancel()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onCancel])

  return (
    <ModalScrim z={Z.nested} onClick={onCancel}>
      <Card
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onClick={(e) => e.stopPropagation()}
        style={{ width: '100%', maxWidth: 380, padding: 24, boxSizing: 'border-box' }}
      >
        <h3
          style={{
            margin: '0 0 8px',
            fontSize: 'var(--text-lg)',
            fontWeight: 'var(--weight-semibold)',
            color: 'var(--text-strong)',
          }}
        >
          {title}
        </h3>
        <p style={{ margin: '0 0 20px', fontSize: 'var(--text-sm)', color: 'var(--text-muted)' }}>
          {message}
        </p>
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onCancel}>
            Cancel
          </Button>
          <Button variant="danger" onClick={onConfirm}>
            {confirmLabel}
          </Button>
        </div>
      </Card>
    </ModalScrim>
  )
}
