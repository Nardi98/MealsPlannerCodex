import React from 'react'

// Long enough that typing a word issues one request, short enough to feel live.
const DEBOUNCE_MS = 300

/**
 * `value`, but only once it has stopped changing for a moment.
 *
 * For search boxes whose settled text drives a server request: the input stays
 * fully controlled and instant, while the query trailing it changes once per
 * pause. The catalog's two screens both search server-side, and a debounce
 * copied into each is a debounce that ends up tuned differently in each.
 *
 * Clearing settles at once, and in the *same* render. "Show me everything
 * again" is a destination, not typing on the way to one, so making it wait out
 * the delay would feel slow -- and settling it through state a render later
 * would still let the consumer's effect fire once on the term just deleted,
 * spending a request to fetch results nobody is waiting for any more.
 */
export function useDebounced(value) {
  const [settled, setSettled] = React.useState(value)

  React.useEffect(() => {
    // Empty still settles here, so typing again debounces from '' rather than
    // from the term that was cleared.
    if (value === '') {
      setSettled('')
      return undefined
    }
    const timer = setTimeout(() => setSettled(value), DEBOUNCE_MS)
    return () => clearTimeout(timer)
  }, [value])

  return value === '' ? '' : settled
}
