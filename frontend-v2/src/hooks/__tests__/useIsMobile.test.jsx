/**
 * @vitest-environment jsdom
 */
import { renderHook, act } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import { useIsMobile } from '../useIsMobile'

const realMatchMedia = window.matchMedia
const realInnerWidth = window.innerWidth

// A controllable `matchMedia` stub. Only the `(max-width: 767px)` query is
// modelled -- the hook asks for nothing else.
function stubMatchMedia(matches) {
  const listeners = new Set()
  const mql = {
    matches,
    media: '(max-width: 767px)',
    addEventListener: (_type, fn) => listeners.add(fn),
    removeEventListener: (_type, fn) => listeners.delete(fn),
  }
  window.matchMedia = vi.fn(() => mql)
  return {
    mql,
    listenerCount: () => listeners.size,
    emit: (next) => {
      mql.matches = next
      listeners.forEach((fn) => fn({ matches: next }))
    },
  }
}

afterEach(() => {
  window.matchMedia = realMatchMedia
  Object.defineProperty(window, 'innerWidth', { value: realInnerWidth, configurable: true })
  vi.restoreAllMocks()
})

test('reports mobile when the max-width query matches', () => {
  stubMatchMedia(true)
  const { result } = renderHook(() => useIsMobile())
  expect(result.current).toBe(true)
})

test('reports desktop when the max-width query does not match', () => {
  stubMatchMedia(false)
  const { result } = renderHook(() => useIsMobile())
  expect(result.current).toBe(false)
})

test('updates when the viewport crosses the breakpoint', () => {
  const media = stubMatchMedia(false)
  const { result } = renderHook(() => useIsMobile())
  expect(result.current).toBe(false)

  act(() => media.emit(true))
  expect(result.current).toBe(true)
})

test('unsubscribes on unmount', () => {
  const media = stubMatchMedia(true)
  const { unmount } = renderHook(() => useIsMobile())
  expect(media.listenerCount()).toBe(1)

  unmount()
  expect(media.listenerCount()).toBe(0)
})

test('falls back to innerWidth when matchMedia is unavailable', () => {
  window.matchMedia = undefined
  Object.defineProperty(window, 'innerWidth', { value: 375, configurable: true })
  const { result: narrow } = renderHook(() => useIsMobile())
  expect(narrow.current).toBe(true)

  Object.defineProperty(window, 'innerWidth', { value: 1280, configurable: true })
  const { result: wide } = renderHook(() => useIsMobile())
  expect(wide.current).toBe(false)
})
