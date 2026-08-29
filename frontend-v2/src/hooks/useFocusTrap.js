import React from 'react'

// Everything the browser will stop on, minus anything explicitly removed from
// the tab order. `:not([disabled])` matters most for the sheet footer's primary
// button, which is disabled while a group is loading.
const FOCUSABLE = [
  'a[href]',
  'button:not([disabled])',
  'input:not([disabled])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(',')

function focusableWithin(container) {
  return Array.from(container.querySelectorAll(FOCUSABLE))
}

// How many traps are open. Refcounted rather than a boolean because a
// ConfirmModal is raised from inside the recipe detail Modal: closing the
// confirmation must not hand scrolling back to a page that is still covered.
let openTraps = 0
let overflowBeforeFirstTrap = ''

function lockPageScroll() {
  if (openTraps === 0) {
    overflowBeforeFirstTrap = document.body.style.overflow
    document.body.style.overflow = 'hidden'
  }
  openTraps += 1
}

function unlockPageScroll() {
  openTraps -= 1
  if (openTraps === 0) document.body.style.overflow = overflowBeforeFirstTrap
}

/**
 * Hold keyboard focus inside `containerRef` while `active`, and stop the page
 * behind from scrolling.
 *
 * `role="dialog" aria-modal="true"` is a promise that focus cannot leave the
 * dialog, and every overlay in this app made that promise without keeping it --
 * closing one left focus on `<body>`, so the next Tab restarted at the top of
 * the page. This is the promise.
 *
 * On activation focus moves to the first focusable descendant, or to the
 * container itself when there is none; on deactivation it returns to whatever
 * was focused before.
 */
export function useFocusTrap(active, containerRef) {
  React.useEffect(() => {
    const container = containerRef.current
    if (!active || !container) return undefined

    const previous = document.activeElement
    const first = focusableWithin(container)[0]
    if (first) {
      first.focus()
    } else {
      // Nothing to land on, but focus must still leave the page behind, or the
      // trap has nothing to trap.
      container.setAttribute('tabindex', '-1')
      container.focus()
    }

    // Queried on every Tab rather than captured once: the filter sheet's
    // content grows and shrinks as its groups expand, so a set captured when
    // the trap opened would go stale on the first tap.
    const onKeyDown = (e) => {
      if (e.key !== 'Tab') return
      const focusable = focusableWithin(container)
      if (focusable.length === 0) return
      const edge = e.shiftKey ? focusable[0] : focusable[focusable.length - 1]
      // Only the edges are handled; anywhere else the browser's own order is
      // better than anything reimplemented here.
      if (document.activeElement !== edge) return
      e.preventDefault()
      ;(e.shiftKey ? focusable[focusable.length - 1] : focusable[0]).focus()
    }
    document.addEventListener('keydown', onKeyDown)
    lockPageScroll()

    return () => {
      document.removeEventListener('keydown', onKeyDown)
      unlockPageScroll()
      if (previous instanceof HTMLElement && previous.isConnected) previous.focus()
    }
  }, [active, containerRef])
}
