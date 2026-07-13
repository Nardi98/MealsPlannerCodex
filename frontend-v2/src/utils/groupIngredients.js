import { CATEGORIES, UNCATEGORIZED } from '../constants/categories'

/**
 * Group ingredients under their categories.
 *
 * Returns an ordered array of `{ category, items }` following the canonical
 * `CATEGORIES` order, with `UNCATEGORIZED` last. An ingredient with N
 * categories appears in N groups; an ingredient with none/empty appears only
 * under `UNCATEGORIZED`. All groups are returned (including empty ones) — the
 * caller decides which to render.
 */
export function groupByCategory(ingredients) {
  const buckets = new Map()
  for (const category of [...CATEGORIES, UNCATEGORIZED]) {
    buckets.set(category, [])
  }

  for (const ing of ingredients || []) {
    const categories = (ing.categories || []).filter((c) => buckets.has(c))
    if (categories.length === 0) {
      buckets.get(UNCATEGORIZED).push(ing)
    } else {
      for (const category of categories) {
        buckets.get(category).push(ing)
      }
    }
  }

  return [...CATEGORIES, UNCATEGORIZED].map((category) => ({
    category,
    items: buckets.get(category),
  }))
}
