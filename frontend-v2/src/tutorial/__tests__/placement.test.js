import { expect, test } from 'vitest'
import { placeBubble, BUBBLE_WIDTH } from '../placement'

const VIEWPORT = { width: 1200, height: 800 }

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
