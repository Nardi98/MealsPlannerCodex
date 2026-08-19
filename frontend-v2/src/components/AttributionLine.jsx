import React from 'react'

/**
 * Permanent credit to the original author of a copied recipe (AT-3 / AT-7).
 *
 * Renders nothing when the recipe was not copied from anyone.
 *
 * Stub placed by Phase 3.0 wiring; the real implementation belongs to 3B.
 * Prop signature is fixed: ({ recipe }).
 */
export function AttributionLine({ recipe }) {
  if (!recipe || !recipe.source_author_username) return null

  return (
    <p
      style={{
        fontFamily: 'var(--font-body)',
        fontSize: 13,
        color: 'var(--text-muted)',
        margin: 0,
      }}
    >
      {`Adapted from ${recipe.source_recipe_title} by @${recipe.source_author_username}`}
    </p>
  )
}

export default AttributionLine
