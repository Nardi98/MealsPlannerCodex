/**
 * @vitest-environment jsdom
 */
import { render, screen, cleanup } from '@testing-library/react'
import { afterEach, expect, test } from 'vitest'
import { Input } from '../Input'

afterEach(() => cleanup())

// iOS Safari auto-zooms when a focused input's font is under 16px, and never
// zooms back out. `text-sm` (14px) is the single biggest reason the site reads
// as a scaled-down desktop on a phone.
test('does not use a sub-16px font size', () => {
  render(<Input aria-label="Search" />)
  expect(screen.getByLabelText('Search').className).not.toContain('text-sm')
})

test('uses a 16px base font so iOS does not zoom on focus', () => {
  render(<Input aria-label="Search" />)
  expect(screen.getByLabelText('Search').className).toContain('text-base')
})

test('is a 44px tap target', () => {
  render(<Input aria-label="Search" />)
  expect(screen.getByLabelText('Search').className).toContain('min-h-11')
})
