import React from 'react'
import { XMarkIcon } from '@heroicons/react/24/outline'
import { Card } from './Card'

// Full-screen dialog shell — dark scrim + centered white Card. Used by the
// Recipes detail dialog; bespoke form modals keep their own markup.
export function Modal({ title, onClose, children, maxWidth = 480 }) {
  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        backgroundColor: 'rgba(12,58,45,0.55)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 60,
      }}
      onClick={onClose}
    >
      <Card
        style={{
          position: 'relative',
          width: '100%',
          maxWidth,
          maxHeight: '90vh',
          overflowY: 'auto',
          padding: 24,
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
    </div>
  )
}
