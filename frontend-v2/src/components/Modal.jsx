import React from 'react'
import { XMarkIcon } from '@heroicons/react/24/outline'
import { Card } from './Card'
import { SCRIM, Z } from '../lib/layers'

// The full-screen wash every takeover shares. Extracted because the mobile
// rules that belong here — keep the card off the screen edges, let a card
// taller than the window scroll — were otherwise a line each author had to
// remember to type, and nine of them had not.
export function ModalScrim({ z = Z.modal, onClick, children }) {
  return (
    <div
      onClick={onClick}
      style={{
        position: 'fixed',
        inset: 0,
        backgroundColor: SCRIM,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 16,
        overflowY: 'auto',
        zIndex: z,
      }}
    >
      {children}
    </div>
  )
}

// Full-screen dialog shell — dark scrim + centered white Card. Used by the
// Recipes detail dialog; bespoke form modals keep their own markup.
export function Modal({ title, onClose, children, maxWidth = 480 }) {
  return (
    <ModalScrim onClick={onClose}>
      <Card
        style={{
          position: 'relative',
          width: '100%',
          maxWidth,
          maxHeight: '90vh',
          overflowY: 'auto',
          padding: 24,
          boxSizing: 'border-box',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {onClose && (
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            style={{
              position: 'absolute',
              top: 16,
              right: 16,
              background: 'none',
              border: 'none',
              cursor: 'pointer',
            }}
          >
            <XMarkIcon className="h-5 w-5" style={{ color: 'var(--text-muted)' }} />
          </button>
        )}
        {title && (
          <h3
            style={{
              margin: '0 0 16px',
              paddingRight: 32,
              fontSize: 'var(--text-lg)',
              fontWeight: 'var(--weight-semibold)',
              color: 'var(--text-strong)',
            }}
          >
            {title}
          </h3>
        )}
        {children}
      </Card>
    </ModalScrim>
  )
}
