import React from 'react'
import { useTour } from './useTour'
import { TourOverlay } from './TourOverlay'
import { TourBubble } from './TourBubble'
import { placeBubble, maxBubbleHeight, maxBubbleWidth } from '../lib/placement'
import { useTutorial } from './tutorialContext'
import { TOURS } from './steps'

// The whole tutorial, as one line in a page: `<PageTour id="recipes" />`.
//
// The steps come from the registry in steps.js by default, so a page names the
// tour and nothing else; `steps` is an override for tests.
//
// `enabled` lets a page hold the tour back until it is worth running — Recipes
// uses it to wait for its first load, so the tour never points at a grid whose
// cards have not arrived yet.
export function PageTour({ id, steps, enabled = true }) {
  const tourSteps = steps ?? TOURS[id]
  const tour = useTour({ id, steps: tourSteps, enabled })
  const { running, step, index, total, isLast, rect, viewport } = tour
  const { register } = useTutorial()
  const [size, setSize] = React.useState(null)
  const bubble = React.useRef(null)

  // Offer this page's tour to the header's replay button for as long as the
  // page is mounted.
  React.useEffect(() => register(tour.start), [register, tour.start])

  // How big the bubble actually turned out. A step with long copy is taller than
  // any estimate, and an estimate that reads low is how the bubble ends up
  // hanging off the bottom of the window — so measure it and place it again.
  // Re-measured whenever the step changes: a longer step must never be placed by
  // the previous one's height. Before paint, so the bubble never shows in the
  // wrong place first — and again on a resize, which reflows the copy.
  React.useLayoutEffect(() => {
    const node = bubble.current
    const box = node ? node.getBoundingClientRect() : null
    setSize(box ? { width: box.width, height: box.height } : null)
  }, [index, running, viewport.width])

  if (!running || !step) return null

  const { top, left, arrow } = placeBubble(rect, step.placement, viewport, size)

  return (
    <TourOverlay rect={rect}>
      <TourBubble
        ref={bubble}
        maxHeight={maxBubbleHeight(viewport)}
        width={maxBubbleWidth(viewport)}
        title={step.title}
        body={step.body}
        index={index}
        total={total}
        isLast={isLast}
        arrow={arrow}
        onNext={tour.next}
        onBack={tour.back}
        onSkip={tour.skip}
        style={{ position: 'fixed', top, left }}
      />
    </TourOverlay>
  )
}
