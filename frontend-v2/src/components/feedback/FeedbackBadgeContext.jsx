import React from 'react'
import { userFeedbackAdminApi } from '../../api/userFeedbackAdminApi'
import { useViewMode } from '../../auth/ViewModeContext'

/**
 * The unread-feedback count behind the admin sidebar's Feedback pill.
 *
 * Owned by the shell, not by `Sidebar`: the sidebar is rendered twice (the
 * desktop column and the mobile drawer), so fetching inside it would ask the
 * server twice. The triage page reaches it through `useFeedbackBadge()` and
 * calls `refresh()` after it changes what is read -- the server is the one
 * source of truth, so the page never does arithmetic on the pill.
 *
 * The default value is what a component outside the provider sees -- no count
 * and a `refresh` that does nothing -- so the page stays renderable on its own.
 */
const FeedbackBadgeContext = React.createContext({ count: undefined, refresh: () => {} })

/**
 * Fetches the count each time the account enters admin mode -- the only mode
 * with a Feedback entry to put it on -- and forgets it on leaving. A failure is
 * silent: the pill is a nicety, and a broken count must never take the shell
 * down with it.
 */
export function FeedbackBadgeProvider({ children }) {
  const enabled = useViewMode().isAdminMode
  const [count, setCount] = React.useState(undefined)
  // Each fetch takes a ticket and only the newest may land, so a slow answer
  // to an older question never overwrites a fresher count.
  const latest = React.useRef(0)

  const fetchCount = React.useCallback(() => {
    const ticket = ++latest.current
    userFeedbackAdminApi
      .unseenCount()
      .then((result) => {
        if (ticket === latest.current) setCount(result?.count)
      })
      .catch(() => {})
  }, [])

  React.useEffect(() => {
    setCount(undefined)
    if (!enabled) return undefined
    fetchCount()
    return () => {
      // Leaving admin mode orphans whatever is still in flight.
      latest.current += 1
    }
  }, [enabled, fetchCount])

  const refresh = React.useCallback(() => {
    if (enabled) fetchCount()
  }, [enabled, fetchCount])

  const value = React.useMemo(() => ({ count, refresh }), [count, refresh])
  return <FeedbackBadgeContext.Provider value={value}>{children}</FeedbackBadgeContext.Provider>
}

// Co-locating the hook with its provider is the standard React Context pattern.
// eslint-disable-next-line react-refresh/only-export-components
export function useFeedbackBadge() {
  return React.useContext(FeedbackBadgeContext)
}
