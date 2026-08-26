import React from 'react'

// The `md` breakpoint, which is where the shell swaps between the drawer and
// the sidebar. Tailwind's `md:` starts at 768px, so "mobile" is everything
// below it -- keep this in sync with the `md:` prefixes in `App.jsx`.
export const MOBILE_QUERY = '(max-width: 767px)'

// One `MediaQueryList` for the whole app, created on first use. `getSnapshot`
// runs on every render of every consumer, so building a fresh one there would
// parse the query string and allocate a native object several times a render.
let query = null
let queriedBy = null

function mediaQuery() {
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') {
    query = null
    queriedBy = null
    return null
  }
  // Keyed on the identity of `matchMedia` itself, not just on the query string:
  // a test that swaps the stub between cases must get the new stub's list, not
  // a cached one whose `media` happens to read the same.
  if (queriedBy !== window.matchMedia) {
    query = window.matchMedia(MOBILE_QUERY)
    queriedBy = window.matchMedia
  }
  return query
}

function read() {
  const mql = mediaQuery()
  // jsdom has no `matchMedia` unless a test stubs one, and neither does SSR.
  // Falling back to `innerWidth` keeps the hook honest instead of pretending
  // every such environment is a desktop.
  if (!mql) return typeof window !== 'undefined' && window.innerWidth < 768
  return mql.matches
}

function subscribe(onChange) {
  const mql = mediaQuery()
  if (!mql) return () => {}
  mql.addEventListener('change', onChange)
  return () => mql.removeEventListener('change', onChange)
}

// True below Tailwind's `md` breakpoint. Use it only where a phone needs
// *different markup* rather than different CSS -- anything expressible as a
// `md:` class belongs in the class list, not here.
export function useIsMobile() {
  return React.useSyncExternalStore(subscribe, read, () => false)
}
