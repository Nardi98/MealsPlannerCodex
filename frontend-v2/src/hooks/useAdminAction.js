import React from 'react'
import { apiErrorText, asSentence } from '../api/catalogApi'

/**
 * The one shape every admin-screen mutation has: busy while it runs, a status
 * line if it has something to report, an alert naming what failed otherwise.
 *
 * `run(what, body)` names the action once -- for the log and for the reader
 * ("add the invites") -- so the two can never describe different things.
 * `body` may resolve to a sentence to report; an edit whose control already
 * shows the result resolves to nothing. `onSuccess` runs after a body that
 * worked (a screen that re-reads its list passes its reload). `run` resolves
 * to whether it worked, so a caller can keep a draft that failed.
 *
 * `setNotice` is the screen's own `{ kind: 'status' | 'alert', text }` setter,
 * because the screen also clears it (the bar's dismiss).
 */
export function useAdminAction(setNotice, { onSuccess } = {}) {
  const [busy, setBusy] = React.useState(false)

  const run = async (what, body) => {
    setBusy(true)
    setNotice(null)
    try {
      const text = await body()
      if (text) setNotice({ kind: 'status', text })
      onSuccess?.()
      return true
    } catch (err) {
      console.error(`Failed to ${what}`, err)
      setNotice({ kind: 'alert', text: `Couldn’t ${what}: ${asSentence(apiErrorText(err))}` })
      return false
    } finally {
      setBusy(false)
    }
  }

  return { busy, run }
}
