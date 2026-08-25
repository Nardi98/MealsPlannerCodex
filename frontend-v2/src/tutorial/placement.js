// Where the bubble goes, given where its target is.
//
// Kept pure and separate from the components so the flipping rules — the part
// that actually breaks on small screens — can be tested without a DOM.

export const BUBBLE_WIDTH = 300
// An estimate, not a measurement: the bubble's real height depends on how long
// the step's copy is, and it only needs to be close enough to decide whether a
// side has room. Being wrong costs a flip, never a bubble off-screen.
export const BUBBLE_HEIGHT = 190
const GAP = 56 // room for the arrow to hang between bubble and target
const MARGIN = 12

function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max)
}

export function placeBubble(rect, placement = 'bottom', viewport) {
  const vw = viewport.width
  const vh = viewport.height

  if (!rect) {
    return {
      top: Math.max(MARGIN, (vh - BUBBLE_HEIGHT) / 2),
      left: (vw - BUBBLE_WIDTH) / 2,
      arrow: null,
    }
  }

  const vertical = placement === 'top' || placement === 'bottom'

  if (vertical) {
    const below = placement === 'bottom'
    const roomBelow = vh - (rect.top + rect.height) >= BUBBLE_HEIGHT + GAP
    const roomAbove = rect.top >= BUBBLE_HEIGHT + GAP
    // Flip only if the preferred side has no room and the other does.
    const useBelow = below ? roomBelow || !roomAbove : !roomAbove && roomBelow
    return {
      top: useBelow
        ? rect.top + rect.height + GAP
        : clamp(rect.top - BUBBLE_HEIGHT - GAP, MARGIN, vh - BUBBLE_HEIGHT - MARGIN),
      left: clamp(rect.left + rect.width / 2 - BUBBLE_WIDTH / 2, MARGIN, vw - BUBBLE_WIDTH - MARGIN),
      arrow: useBelow ? 'up' : 'down',
    }
  }

  const right = placement === 'right'
  const roomRight = vw - (rect.left + rect.width) >= BUBBLE_WIDTH + GAP
  const roomLeft = rect.left >= BUBBLE_WIDTH + GAP
  const useRight = right ? roomRight || !roomLeft : !roomLeft && roomRight
  return {
    top: clamp(rect.top + rect.height / 2 - BUBBLE_HEIGHT / 2, MARGIN, vh - BUBBLE_HEIGHT - MARGIN),
    left: useRight
      ? clamp(rect.left + rect.width + GAP, MARGIN, vw - BUBBLE_WIDTH - MARGIN)
      : clamp(rect.left - BUBBLE_WIDTH - GAP, MARGIN, vw - BUBBLE_WIDTH - MARGIN),
    arrow: useRight ? 'left' : 'right',
  }
}
