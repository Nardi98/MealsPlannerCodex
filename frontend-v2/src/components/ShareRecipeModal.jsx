import React from 'react'
import { Modal } from './Modal'

/**
 * Share dialog for a single recipe (SH-7 / SH-8 / SH-9 / SH-12 / SH-20).
 *
 * Stub placed by Phase 3.0 wiring; the real implementation belongs to 3A.
 * Prop signature is fixed: ({ recipe, open, onClose }).
 */
export function ShareRecipeModal({ recipe, open, onClose }) {
  if (!open) return null

  return (
    <Modal title="Share recipe" onClose={onClose}>
      <p style={{ margin: 0, fontSize: 'var(--text-sm)', color: 'var(--text-muted)' }}>
        {recipe ? recipe.title : 'No recipe selected.'}
      </p>
    </Modal>
  )
}

export default ShareRecipeModal
