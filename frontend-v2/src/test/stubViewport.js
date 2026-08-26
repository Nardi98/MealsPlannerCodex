import { vi } from 'vitest'
import { MOBILE_QUERY } from '../hooks/useIsMobile'

// Choose a viewport for `useIsMobile`. jsdom does not evaluate media queries,
// so components that branch on the breakpoint need `matchMedia` stubbed; the
// query string comes from the hook so the two can never disagree.
export function stubViewport(mobile) {
  window.matchMedia = vi.fn(() => ({
    matches: mobile,
    media: MOBILE_QUERY,
    addEventListener: () => {},
    removeEventListener: () => {},
  }))
}
