import React from 'react'

/**
 * Permanent credit to the original author of a copied recipe (AT-3 / AT-7).
 *
 * Renders nothing when the recipe was not copied from anyone.
 *
 * Prop signature is fixed: ({ recipe }).
 */
function creditText(recipe) {
  // UI-10: a copy of a catalog recipe credits the library, and is checked first
  // so the system account's handle can never render. FC-4: only a branch -- a
  // copy from a real user keeps its @handle credit below.
  if (recipe?.from_library) return 'From the recipe library'
  if (recipe?.source_author_username) {
    return `Adapted from ${recipe.source_recipe_title} by @${recipe.source_author_username}`
  }
  return null
}

export function AttributionLine({ recipe }) {
  const text = creditText(recipe)
  if (!text) return null

  return (
    <p
      style={{
        fontFamily: 'var(--font-body)',
        fontSize: 13,
        color: 'var(--text-muted)',
        margin: 0,
      }}
    >
      {text}
    </p>
  )
}

export default AttributionLine
