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

// 44 x 44, not 44 tall: a one-character label inside `px-3` came to about 28px
// wide, which is how the shopping list's people steppers met the rule in one
// dimension only.
test('every size is as wide as it is tall', () => {
  for (const [size, min] of [['sm', 'min-w-9'], ['md', 'min-w-11'], ['lg', 'min-w-11']]) {
    cleanup()
    render(<Button size={size}>+</Button>)
    expect(screen.getByRole('button').className).toContain(min)
  }
})

test('variants and legacy aliases still resolve to a background colour', () => {
  for (const variant of ['primary', 'danger', 'accent', 'secondary', 'a1', 'a2']) {
    cleanup()
    render(<Button variant={variant}>Go</Button>)
    expect(screen.getByRole('button').style.backgroundColor).not.toBe('')
  }
})
