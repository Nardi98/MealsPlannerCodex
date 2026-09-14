import React from 'react'

/**
 * Run `onOutside` while `active`, whenever a mousedown lands outside the
 * element `ref` points at. The companion of `useEscapeKey` for popovers.
 */
export function useOnClickOutside(ref, active, onOutside) {
  React.useEffect(() => {
    if (!active) return undefined
    const onDown = (e) => {
      if (ref.current && !ref.current.contains(e.target)) onOutside()
    }
    document.addEventListener('mousedown', onDown)
    return () => document.removeEventListener('mousedown', onDown)
  }, [ref, active, onOutside])
}
