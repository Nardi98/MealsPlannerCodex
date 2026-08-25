import React from 'react'
import { useTour } from './useTour'
import { TourOverlay } from './TourOverlay'
import { TourBubble } from './TourBubble'
import { placeBubble } from './placement'
import { useTutorial } from './tutorialContext'
import { TOURS } from './steps'

// The whole tutorial, as one line in a page: `<PageTour id="recipes" />`.
//
// The steps come from the registry in steps.js by default, so a page names the
// tour and nothing else; `steps` is an override for tests.
//
// `enabled` lets a page hold the tour back until it is worth running — Recipes
// uses it to let the starter-recipes modal go first, so a brand-new account
// isn't taught about a recipe grid that is still empty.
export function PageTour({ id, steps, enabled = true }) {
  const tourSteps = steps ?? TOURS[id]
  const tour = useTour({ id, steps: tourSteps, enabled })
  const { running, step, index, total, isLast, rect, viewport } = tour
  const { register } = useTutorial()

  // Offer this page's tour to the header's replay button for as long as the
  // page is mounted.
  React.useEffect(() => register(tour.start), [register, tour.start])

  if (!running || !step) return null

  const { top, left, arrow } = placeBubble(rect, step.placement, viewport)

  return (
    <TourOverlay rect={rect}>
      <TourBubble
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
