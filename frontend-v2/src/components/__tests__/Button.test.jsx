/**
 * @vitest-environment jsdom
 */
import { render, screen, cleanup } from '@testing-library/react'
import { afterEach, expect, test } from 'vitest'
import { Button } from '../Button'

afterEach(() => cleanup())

// Design guide §8.4: every interactive control is at least 44x44. `min-h-11`
// is Tailwind's 44px; `sm` is allowed to be a little shorter for dense rows
// but must still clear a fingertip.
test('the default size is a 44px tap target', () => {
  render(<Button>Save</Button>)
  expect(screen.getByRole('button').className).toContain('min-h-11')
})

test('the large size is a 44px tap target', () => {
  render(<Button size="lg">Save</Button>)
  expect(screen.getByRole('button').className).toContain('min-h-11')
})

test('the small size still has a minimum height', () => {
  render(<Button size="sm">Save</Button>)
  expect(screen.getByRole('button').className).toContain('min-h-9')
})

test('variants and legacy aliases still resolve to a background colour', () => {
  for (const variant of ['primary', 'danger', 'accent', 'secondary', 'a1', 'a2']) {
    cleanup()
    render(<Button variant={variant}>Go</Button>)
    expect(screen.getByRole('button').style.backgroundColor).not.toBe('')
  }
})
