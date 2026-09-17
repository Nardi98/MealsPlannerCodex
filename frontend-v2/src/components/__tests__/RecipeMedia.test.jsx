/**
 * @vitest-environment jsdom
 */
import { render, screen, cleanup } from '@testing-library/react'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import '@testing-library/jest-dom/vitest'
import { RecipeMedia } from '..'

beforeEach(() => {
  // The dish-glyph Icon fetches SVGs from a CDN; keep tests hermetic.
  globalThis.fetch = vi.fn(() => Promise.reject(new Error('no network')))
})

afterEach(() => {
  vi.restoreAllMocks()
  cleanup()
})

test('draws the recipe photo, filling its parent with the given rounding', () => {
  render(<RecipeMedia recipe={{ title: 'Ribollita', course: 'main', image_url: 'http://img/a.png' }} rounded="4px" />)

  const img = screen.getByAltText('Ribollita photo')
  expect(img).toHaveAttribute('src', 'http://img/a.png')
  expect(img).toHaveStyle({ position: 'absolute', objectFit: 'cover', borderRadius: '4px' })
})

test('without a photo it draws a decorative placeholder tile instead', () => {
  const { container } = render(<RecipeMedia recipe={{ title: 'Ribollita', course: 'main', image_url: null }} />)

  expect(screen.queryByRole('img', { name: /photo/ })).toBeNull()
  const tile = container.firstChild
  expect(tile).toHaveAttribute('aria-hidden', 'true')
  expect(tile).toHaveStyle({ position: 'absolute', display: 'flex' })
})
