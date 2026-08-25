import React from 'react'
import { isTourDone, markTourDone, markAllToursDone } from './tourStorage'

function sameFrame(a, b) {
  if (a === b) return true
  if (!a || !b) return false
  return a.top === b.top && a.left === b.left && a.width === b.width && a.height === b.height
}

function currentViewport() {
  return typeof window === 'undefined'
    ? { width: 1024, height: 768 }
    : { width: window.innerWidth, height: window.innerHeight }
}

// Runtime state for one page's tour: which step is showing, and where on screen
// the thing it is pointing at currently is.
//
// The rect is tracked here rather than in the overlay so that "the target is
// missing" has one meaning for every consumer: `rect === null`. A step whose
// anchor is absent (an empty recipe book, a week with no plan yet) still shows —
// it just renders centered and arrow-less. The step count deliberately does not
// shrink, so the dots mean the same thing for every user.
export function useTour({ id, steps, enabled = true }) {
  const [index, setIndex] = React.useState(0)
  const [running, setRunning] = React.useState(false)
  const [rect, setRect] = React.useState(null)
  // Measured alongside the rect, from the same pass: placement needs both, and
  // one listener answering both questions beats two that disagree.
  const [viewport, setViewport] = React.useState(currentViewport)
  const autoStarted = React.useRef(false)

  const total = steps.length
  const step = running ? steps[index] : null
  const isLast = index === total - 1

  const start = React.useCallback(() => {
    setIndex(0)
    setRunning(true)
  }, [])

  // Auto-start is one-shot per mount: once this tour has run (or been declined)
  // a re-render must not restart it, and neither must the `enabled` gate
  // flickering as the page loads.
  React.useEffect(() => {
    if (autoStarted.current || !enabled || total === 0) return
    if (isTourDone(id)) {
      autoStarted.current = true
      return
    }
    autoStarted.current = true
    start()
  }, [enabled, id, start, total])

  const finish = React.useCallback(() => {
    setRunning(false)
    markTourDone(id)
  }, [id])

  const next = React.useCallback(() => {
    setIndex((i) => {
      if (i >= total - 1) {
        finish()
        return i
      }
      return i + 1
    })
  }, [finish, total])

  const back = React.useCallback(() => {
    setIndex((i) => Math.max(0, i - 1))
  }, [])

  const skip = React.useCallback(() => {
    setRunning(false)
    markAllToursDone()
  }, [])

  // The target can move under the tour without React knowing — a scroll, a
  // resize, a card finishing its load — so the frame is re-measured on those
  // events rather than captured once.
  //
  // Scrolling fires this a lot, and almost every one of those events leaves the
  // anchor exactly where it was, so the measurement is coalesced to one per
  // animation frame and only commits when something actually moved. Without
  // that, every scroll event re-renders the overlay and its panels.
  React.useEffect(() => {
    if (!step) {
      setRect(null)
      return undefined
    }
    // Cached so the common case costs a getBoundingClientRect and nothing else.
    let el = null
    let frame = 0

    const measure = () => {
      frame = 0
      if (!el || !el.isConnected) el = document.querySelector(step.target)
      const box = el ? el.getBoundingClientRect() : null
      const next = box
        ? { top: box.top, left: box.left, width: box.width, height: box.height }
        : null
      setRect((prev) => (sameFrame(prev, next) ? prev : next))
      setViewport((prev) =>
        prev.width === window.innerWidth && prev.height === window.innerHeight
          ? prev
          : { width: window.innerWidth, height: window.innerHeight },
      )
    }

    const schedule = () => {
      if (frame) return
      frame = window.requestAnimationFrame(measure)
    }

    measure()
    // A late-rendering anchor would otherwise be measured as missing forever.
    const settle = window.setTimeout(measure, 120)
    window.addEventListener('resize', schedule)
    window.addEventListener('scroll', schedule, { capture: true, passive: true })
    return () => {
      window.clearTimeout(settle)
      if (frame) window.cancelAnimationFrame(frame)
      window.removeEventListener('resize', schedule)
      window.removeEventListener('scroll', schedule, { capture: true })
    }
  }, [step])

  return { running, step, index, total, isLast, rect, viewport, start, next, back, skip }
}
