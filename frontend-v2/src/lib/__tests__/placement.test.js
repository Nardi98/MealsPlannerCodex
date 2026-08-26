import { expect, test } from 'vitest'
import { placeBubble, maxBubbleWidth, BUBBLE_WIDTH, BUBBLE_HEIGHT, MARGIN } from '../placement'

const VIEWPORT = { width: 1200, height: 800 }
// A caller that draws no arrow and wants the bubble close to its target.
const SMALL_GAP = 10

test('a bubble placed below sits under the target and points up at it', () => {
  const got = placeBubble({ top: 100, left: 400, width: 200, height: 50 }, 'bottom', VIEWPORT)
  expect(got.arrow).toBe('up')
  expect(got.top).toBeGreaterThan(150)
})

test('a bubble placed above sits over the target and points down at it', () => {
  const got = placeBubble({ top: 500, left: 400, width: 200, height: 50 }, 'top', VIEWPORT)
  expect(got.arrow).toBe('down')
  expect(got.top).toBeLessThan(500)
})

test('bottom placement flips to top when there is no room below', () => {
  const got = placeBubble({ top: 700, left: 400, width: 200, height: 60 }, 'bottom', VIEWPORT)
  expect(got.arrow).toBe('down')
})

test('right placement flips to left when there is no room to the right', () => {
  const got = placeBubble({ top: 300, left: 1050, width: 120, height: 40 }, 'right', VIEWPORT)
  expect(got.arrow).toBe('right')
  expect(got.left).toBeLessThan(1050)
})

test('the bubble is kept inside the viewport horizontally', () => {
  const near = placeBubble({ top: 300, left: 4, width: 40, height: 40 }, 'bottom', VIEWPORT)
  expect(near.left).toBeGreaterThanOrEqual(0)
  const far = placeBubble({ top: 300, left: 1180, width: 40, height: 40 }, 'bottom', VIEWPORT)
  expect(far.left + BUBBLE_WIDTH).toBeLessThanOrEqual(VIEWPORT.width)
})

test('with no target the bubble is centered and has no arrow', () => {
  const got = placeBubble(null, 'bottom', VIEWPORT)
  expect(got.arrow).toBe(null)
  expect(got.left).toBeCloseTo((VIEWPORT.width - BUBBLE_WIDTH) / 2)
})

// The bug this file's clamping exists for: the first Recipes step used to point
// at the whole recipe grid, and the bubble was placed below its *bottom* — a
// couple of thousand pixels under a viewport it can never scroll back into.
test('a target taller than the viewport still leaves the bubble on screen', () => {
  const got = placeBubble({ top: 120, left: 300, width: 800, height: 3000 }, 'bottom', VIEWPORT)
  expect(got.top).toBeGreaterThanOrEqual(0)
  expect(got.top + BUBBLE_HEIGHT).toBeLessThanOrEqual(VIEWPORT.height)
})

test('a target at the very bottom edge still leaves the bubble on screen', () => {
  const got = placeBubble({ top: 780, left: 300, width: 200, height: 40 }, 'bottom', VIEWPORT)
  expect(got.top).toBeGreaterThanOrEqual(0)
  expect(got.top + BUBBLE_HEIGHT).toBeLessThanOrEqual(VIEWPORT.height)
})

test('a measured bubble is placed by its real height, not the estimate', () => {
  const tall = { width: BUBBLE_WIDTH, height: 700 }
  const got = placeBubble({ top: 100, left: 300, width: 200, height: 40 }, 'bottom', VIEWPORT, tall)
  expect(got.top + tall.height).toBeLessThanOrEqual(VIEWPORT.height)
})

test('a bubble taller than the viewport is pinned to the top rather than overflowing it', () => {
  const huge = { width: BUBBLE_WIDTH, height: 2000 }
  const got = placeBubble({ top: 300, left: 300, width: 200, height: 40 }, 'bottom', VIEWPORT, huge)
  expect(got.top).toBe(MARGIN)
})

test('the arrow is dropped when clamping moved the bubble off the target', () => {
  // Nothing to point at: the bubble had to be pulled back up over the target.
  const got = placeBubble({ top: 120, left: 300, width: 800, height: 3000 }, 'bottom', VIEWPORT)
  expect(got.arrow).toBe(null)
})

test('the arrow survives a purely horizontal clamp', () => {
  const got = placeBubble({ top: 100, left: 1180, width: 40, height: 40 }, 'bottom', VIEWPORT)
  expect(got.arrow).toBe('up')
})

test('a custom gap places the bubble closer to the target than the default', () => {
  const rect = { top: 500, left: 400, width: 200, height: 50 }
  const dflt = placeBubble(rect, 'top', VIEWPORT)
  const tight = placeBubble(rect, 'top', VIEWPORT, undefined, SMALL_GAP)
  expect(tight.top).toBeGreaterThan(dflt.top)
  expect(tight.top + BUBBLE_HEIGHT).toBe(rect.top - SMALL_GAP)
})

test('a custom gap is also what the flip decision is made against', () => {
  // Room for the bubble plus a small gap, but not plus the tour's big one.
  const rect = { top: BUBBLE_HEIGHT + 30, left: 400, width: 200, height: 50 }
  expect(placeBubble(rect, 'top', VIEWPORT).arrow).toBe('up')
  expect(placeBubble(rect, 'top', VIEWPORT, undefined, SMALL_GAP).arrow).toBe('down')
})

// --- Narrow viewports -------------------------------------------------------
//
// `BUBBLE_WIDTH` used to be a hard 300px, which on a 320px phone left 20px of
// slack and no room at all for a `left`/`right` placement to resolve.
const PHONE = { width: 320, height: 640 }

test('the bubble narrows to fit a phone viewport', () => {
  expect(maxBubbleWidth(PHONE)).toBe(320 - 2 * MARGIN)
})

test('the bubble never grows past its natural width on a wide viewport', () => {
  expect(maxBubbleWidth({ width: 1440, height: 900 })).toBe(BUBBLE_WIDTH)
})

test('a side placement falls back to vertical when neither side has room', () => {
  // A full-width target on a phone: nothing fits to its left or its right.
  const rect = { top: 200, left: 0, width: 320, height: 40 }
  const size = { width: maxBubbleWidth(PHONE), height: 190 }

  const placed = placeBubble(rect, 'right', PHONE, size)

  expect(placed.left).toBeGreaterThanOrEqual(MARGIN)
  expect(placed.left + size.width).toBeLessThanOrEqual(PHONE.width - MARGIN)
  // It moved above or below the target rather than pinning itself on top of it.
  expect(['up', 'down']).toContain(placed.arrow)
})

test('a bubble placed on a phone stays inside the viewport', () => {
  const rect = { top: 40, left: 260, width: 44, height: 44 }
  const size = { width: maxBubbleWidth(PHONE), height: 190 }

  const { top, left } = placeBubble(rect, 'bottom', PHONE, size)

  expect(left).toBeGreaterThanOrEqual(MARGIN)
  expect(left + size.width).toBeLessThanOrEqual(PHONE.width - MARGIN)
  expect(top).toBeGreaterThanOrEqual(MARGIN)
})
