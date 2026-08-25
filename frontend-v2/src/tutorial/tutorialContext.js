import React from 'react'

// The context and its hook live apart from the components that use them so the
// provider file exports components only — Fast Refresh cannot reload a module
// that mixes the two.

export const TutorialContext = React.createContext(null)

// Outside a provider (a page rendered on its own in a test) the tour still
// runs; it just has no replay button. That is why this falls back to inert
// handlers instead of throwing.
const NO_PROVIDER = { register: () => () => {}, replay: () => {}, hasTour: false }

export function useTutorial() {
  return React.useContext(TutorialContext) ?? NO_PROVIDER
}
