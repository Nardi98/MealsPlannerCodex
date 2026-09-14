import React from 'react'
import { FunnelIcon } from '@heroicons/react/24/outline'
import { Button } from './Button'
import BottomSheet from './BottomSheet'
import RecipeFilters from './RecipeFilters'
import { useEscapeKey } from '../hooks/useEscapeKey'
import { useIsMobile } from '../hooks/useIsMobile'
import { useOnClickOutside } from '../hooks/useOnClickOutside'

/**
 * The funnel button that opens the recipe filters: a popover on desktop, a
 * bottom sheet on a phone. Shared by the Recipes and Discover pages.
 *
 * `groups` is `RecipeFilters`' list; `activeCount` badges the funnel;
 * `resultCount` is what the sheet's footer button reports. `popoverPosition`
 * holds the popover's positioning classes, which differ per page, and `tour`
 * is an optional `data-tour` anchor for the funnel.
 */
export default function RecipeFilterControl({
  groups,
  activeCount,
  resultCount,
  popoverPosition = 'right-0',
  tour,
}) {
  const isMobile = useIsMobile()
  const [showFilters, setShowFilters] = React.useState(false)

  // The desktop popover dismisses on Escape and outside click, as
  // DateRangePicker does; the sheet handles its own Escape.
  const filterRef = React.useRef(null)
  const closeFilters = React.useCallback(() => setShowFilters(false), [])
  useEscapeKey(showFilters && !isMobile, closeFilters)
  useOnClickOutside(filterRef, showFilters && !isMobile, closeFilters)

  return (
    <>
      <div className="relative" ref={filterRef}>
        <Button
          variant="ghost"
          aria-label="Filter"
          data-tour={tour}
          className="relative"
          onClick={() => setShowFilters((s) => !s)}
          Icon={FunnelIcon}
        >
          {activeCount > 0 && (
            <span
              className="absolute -right-1 -top-1 flex h-5 min-w-5 items-center justify-center rounded-full px-1 text-xs"
              style={{ backgroundColor: 'var(--c-neg)', color: '#fff' }}
            >
              {activeCount}
            </span>
          )}
        </Button>
        {showFilters && !isMobile && (
          <div
            // 20rem, up from 14: the chips inside grew from 13px checkboxes to
            // `px-4 min-h-11`, and a long ingredient name wrapped three
            // times in 224px. Still clamped to the viewport, per §8.
            className={`absolute ${popoverPosition} z-10 mt-2 w-[min(20rem,calc(100vw-2rem))] rounded-2xl border bg-white p-2`}
            style={{ borderColor: 'var(--border-default)' }}
          >
            <RecipeFilters groups={groups} />
          </div>
        )}
      </div>
      {showFilters && isMobile && (
        <BottomSheet
          title="Filters"
          onClose={closeFilters}
          footer={
            <Button variant="accent" className="w-full" onClick={closeFilters}>
              {`Show ${resultCount} ${resultCount === 1 ? 'recipe' : 'recipes'}`}
            </Button>
          }
        >
          <RecipeFilters groups={groups} />
        </BottomSheet>
      )}
    </>
  )
}
