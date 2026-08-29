import React from 'react'

/**
 * Run `onEscape` while `active`, whenever Escape is pressed.
 *
 * Every dismissable surface was hand-rolling this same effect -- the listener,
 * the key comparison and the cleanup -- and each one independently remembered
 * to remove the listener. Six copies had accumulated before this existed.
 */
export function useEscapeKey(active, onEscape) {
  React.useEffect(() => {
    if (!active) return undefined
    const onKey = (e) => {
      if (e.key === 'Escape') onEscape()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [active, onEscape])
}
