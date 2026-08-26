// Where the bubble goes, given where its target is.
//
// Kept pure and separate from the components so the flipping rules — the part
// that actually breaks on small screens — can be tested without a DOM.

// The bubble's natural width. It is a maximum, not a fixed size: see
// `maxBubbleWidth`, which narrows it on phones too small to hold it.
export const BUBBLE_WIDTH = 300
// The starting guess, used for the first paint and by callers that have nothing
// better. Once the bubble has been rendered its real size is measured and passed
// in as `size`: a step with long copy is taller than any estimate, and guessing
// low is how a bubble ends up hanging off the bottom edge.
export const BUBBLE_HEIGHT = 190
export const MARGIN = 12
// How far a bubble sits from its target. The default leaves room for the tour's
// squiggly arrow to hang between the two; callers that draw no arrow pass their
// own, smaller `gap`.
const ARROW_GAP = 56

// How tall the bubble may render. The same budget the placement below works to,
// so the bubble cannot be sized by one rule and positioned by another — `100vh`
// in CSS and `window.innerHeight` here disagree by a URL bar on mobile.
export function maxBubbleHeight(viewport) {
  return Math.max(0, viewport.height - 2 * MARGIN)
}

// How wide the bubble may render. A hard 300px left 20px of slack on a 320px
// phone and nothing at all for a side placement to work with, so the bubble
// gives up width before it gives up its margins.
export function maxBubbleWidth(viewport) {
  return Math.max(0, Math.min(BUBBLE_WIDTH, viewport.width - 2 * MARGIN))
}

// Keep `value` inside the viewport along one axis, and say whether it had to
// move: a bubble that was pulled back over its target has nothing left to point
// at. A bubble too big to fit at all is pinned to the near edge rather than
// centred on an impossible range — it scrolls internally (see TourBubble), so
// its top edge is the useful one.
function fit(value, extent, limit) {
  const max = limit - extent - MARGIN
  const fitted = max <= MARGIN ? MARGIN : Math.min(Math.max(value, MARGIN), max)
  return { value: fitted, clamped: fitted !== value }
}

export function placeBubble(rect, placement = 'bottom', viewport, size, gap = ARROW_GAP) {
  const vw = viewport.width
  const vh = viewport.height
  const w = size?.width || maxBubbleWidth(viewport)
  const h = size?.height || BUBBLE_HEIGHT

  if (!rect) {
    return {
      top: fit((vh - h) / 2, h, vh).value,
      left: fit((vw - w) / 2, w, vw).value,
      arrow: null,
    }
  }

  const vertical = placement === 'top' || placement === 'bottom'

  if (vertical) {
    const below = placement === 'bottom'
    const roomBelow = vh - (rect.top + rect.height) >= h + gap
    const roomAbove = rect.top >= h + gap
    // Flip only if the preferred side has no room and the other does.
    const useBelow = below ? roomBelow || !roomAbove : !roomAbove && roomBelow
    const top = fit(useBelow ? rect.top + rect.height + gap : rect.top - h - gap, h, vh)
    return {
      top: top.value,
      left: fit(rect.left + rect.width / 2 - w / 2, w, vw).value,
      // A target taller than the screen (or one hard against an edge) leaves no
      // side with room, so the bubble gets pulled back over it. The arrow would
      // then point at whatever happens to be under the bubble: drop it instead.
      // A horizontal clamp is harmless — the bubble is still on the right side.
      arrow: top.clamped ? null : (useBelow ? 'up' : 'down'),
    }
  }

  const right = placement === 'right'
  const roomRight = vw - (rect.left + rect.width) >= w + gap
  const roomLeft = rect.left >= w + gap

  // Neither side fits — the usual case on a phone, where almost every target is
  // as wide as the screen. Placing sideways anyway would clamp the bubble back
  // over its target and drop the arrow; going vertical keeps both.
  if (!roomRight && !roomLeft) return placeBubble(rect, 'bottom', viewport, size, gap)

  const useRight = right ? roomRight || !roomLeft : !roomLeft && roomRight
  const left = fit(useRight ? rect.left + rect.width + gap : rect.left - w - gap, w, vw)
  return {
    top: fit(rect.top + rect.height / 2 - h / 2, h, vh).value,
    left: left.value,
    arrow: left.clamped ? null : (useRight ? 'left' : 'right'),
  }
}
