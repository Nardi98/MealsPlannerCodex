import React from 'react'
import { userFeedbackAdminApi } from '../../api/userFeedbackAdminApi'
import { useViewMode } from '../../auth/ViewModeContext'

/**
 * The unread-feedback count behind the admin sidebar's Feedback pill.
 *
 * Owned by the shell, not by `Sidebar`: the sidebar is rendered twice (the
 * desktop column and the mobile drawer), so fetching inside it would ask the
 * server twice. The triage page reaches it through `useFeedbackBadge()` to take
 * one off as it reads an item, or put one back when it marks one unread.
 *
 * The default value is what a component outside the provider sees -- no count
 * and an `adjust` that does nothing -- so the page stays renderable on its own.
 */
const FeedbackBadgeContext = React.createContext({ count: undefined, adjust: () => {} })

/**
 * Fetches the count each time the account enters admin mode -- the only mode
 * with a Feedback entry to put it on -- and forgets it on leaving. A failure is
 * silent: the pill is a nicety, and a broken count must never take the shell
 * down with it.
 */
export function FeedbackBadgeProvider({ children }) {
  const enabled = useViewMode().isAdminMode
  const [count, setCount] = React.useState(undefined)

  React.useEffect(() => {
    setCount(undefined)
    if (!enabled) return undefined
    let stale = false
    userFeedbackAdminApi
      .unseenCount()
      .then((result) => {
        if (!stale) setCount(result?.count)
      })
      .catch(() => {})
    return () => {
      stale = true
    }
  }, [enabled])

  // Never below zero: a decrement racing a fresh fetch must not show "-1".
  const adjust = React.useCallback(
    (delta) => setCount((current) => (current === undefined ? current : Math.max(0, current + delta))),
    [],
  )

  const value = React.useMemo(() => ({ count, adjust }), [count, adjust])
  return <FeedbackBadgeContext.Provider value={value}>{children}</FeedbackBadgeContext.Provider>
}

// Co-locating the hook with its provider is the standard React Context pattern.
// eslint-disable-next-line react-refresh/only-export-components
export function useFeedbackBadge() {
  return React.useContext(FeedbackBadgeContext)
}
