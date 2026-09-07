export const SORT_OPTIONS = [
  { value: 'default', label: 'Default' },
  { value: 'score', label: 'Score' },
  { value: 'name', label: 'Name' },
  { value: 'course', label: 'Type' },
]

// The order courses read in on a menu. Spelled out rather than taken from
// `COURSE_ICONS`, whose key order is incidental — it lists side before
// first-course, which is not how a meal is served.
const COURSE_ORDER = ['main', 'first-course', 'side', 'dessert']

const COURSE_RANK = new Map(COURSE_ORDER.map((course, index) => [course, index]))

// Course is free text on the server, so anything unrecognised sorts after the
// known ones rather than landing at an arbitrary rank.
const courseRank = (recipe) =>
  COURSE_RANK.has(recipe.course) ? COURSE_RANK.get(recipe.course) : COURSE_ORDER.length

// Built once: `localeCompare` with options rebuilds a collator on every call,
// and a comparator is called O(n log n) times per sort.
const collator = new Intl.Collator(undefined, { sensitivity: 'base' })

const byTitle = (a, b) => collator.compare(a.title || '', b.title || '')

/** Score's useful first look is the best recipes; the others read A→Z. */
export function defaultDirectionFor(key) {
  return key === 'score' ? 'desc' : 'asc'
}

/**
 * Order a recipe list for display. Returns a new array; `default` hands back
 * the server's own order untouched.
 */
export function sortRecipes(recipes, { key, direction } = {}) {
  if (key === 'default' || !key) return [...recipes]
  const flip = direction === 'desc' ? -1 : 1

  if (key === 'score') {
    return [...recipes].sort((a, b) => {
      // A score is only meaningful once the planner has learned one: an
      // unscored recipe is unknown, not bad, so it stays in the tail either
      // way and its ordering is deliberately not flipped.
      if (a.score == null || b.score == null) return (a.score == null) - (b.score == null)
      return (a.score - b.score) * flip
    })
  }
  if (key === 'name') {
    return [...recipes].sort((a, b) => byTitle(a, b) * flip)
  }
  // Grouping is what the user asked for, so only the group order flips —
  // titles stay A→Z inside each group either way.
  return [...recipes].sort(
    (a, b) => (courseRank(a) - courseRank(b)) * flip || byTitle(a, b),
  )
}
