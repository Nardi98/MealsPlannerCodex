import React from 'react'

/**
 * `useState` that remembers its value in localStorage.
 *
 * Reading `window.localStorage` itself throws in browsers set to block site
 * data — not only the get/set calls — so every access is guarded and a failure
 * degrades to plain component state. A remembered UI preference must never be
 * able to take down the view it belongs to.
 */
export function usePersistedState(key, fallback, isValid = () => true) {
  const [value, setValue] = React.useState(() => {
    try {
      const stored = window.localStorage.getItem(key)
      return stored !== null && isValid(stored) ? stored : fallback
    } catch {
      return fallback
    }
  })

  const persist = React.useCallback(
    (next) => {
      setValue(next)
      try {
        window.localStorage.setItem(key, next)
      } catch {
        // Storage is a convenience; losing it must not break the control.
      }
    },
    [key],
  )

  return [value, persist]
}
