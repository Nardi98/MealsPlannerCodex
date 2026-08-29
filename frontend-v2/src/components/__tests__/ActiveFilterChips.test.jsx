/**
 * @vitest-environment jsdom
 */
import { render, screen, fireEvent, cleanup } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import '@testing-library/jest-dom/vitest'
import ActiveFilterChips from '../ActiveFilterChips'

afterEach(() => cleanup())

const filters = [
  { value: 'vegetarian', onRemove: () => {} },
  { value: 'quick', onRemove: () => {} },
]

test('renders nothing when no filter is active', () => {
  const { container } = render(<ActiveFilterChips filters={[]} onClearAll={() => {}} />)
  expect(container).toBeEmptyDOMElement()
})

test('a chip removes its own filter', () => {
  const onRemove = vi.fn()
  render(
    <ActiveFilterChips filters={[{ value: 'vegetarian', onRemove }]} onClearAll={() => {}} />,
  )

  fireEvent.click(screen.getByRole('button', { name: 'Remove filter vegetarian' }))

  expect(onRemove).toHaveBeenCalledTimes(1)
})

// Design guide §8.4. These chips mirror the ones inside the filter sheet,
// which are 44px; being the page-level copy is no reason to be smaller.
test('every chip is a 44px tap target', () => {
  render(<ActiveFilterChips filters={filters} onClearAll={() => {}} />)

  for (const chip of screen.getAllByRole('button')) {
    expect(chip.className).toContain('min-h-11')
  }
})
