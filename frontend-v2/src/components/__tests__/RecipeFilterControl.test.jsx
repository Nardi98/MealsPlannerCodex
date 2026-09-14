/**
 * @vitest-environment jsdom
 */
import { render, screen, fireEvent, within, cleanup } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import '@testing-library/jest-dom/vitest'
import { RecipeFilterControl } from '..'
import { stubViewport } from '../../test/stubViewport'

afterEach(() => {
  vi.restoreAllMocks()
  cleanup()
})

const GROUPS = [{ label: 'Course', options: ['main', 'side'], selected: [], onSelect: () => {}, clear: () => {} }]

const renderControl = (props = {}) =>
  render(<RecipeFilterControl groups={GROUPS} activeCount={0} resultCount={3} {...props} />)

test('the funnel shows the active filter count only when there is one', () => {
  renderControl()
  expect(screen.getByLabelText('Filter')).not.toHaveTextContent(/\d/)
  cleanup()

  renderControl({ activeCount: 2 })
  expect(screen.getByLabelText('Filter')).toHaveTextContent('2')
})

test('passes the tour anchor to the funnel button', () => {
  renderControl({ tour: 'recipes-filter' })
  expect(screen.getByLabelText('Filter')).toHaveAttribute('data-tour', 'recipes-filter')
})

test('on desktop it toggles a popover with the given position classes', () => {
  stubViewport(false)
  renderControl({ popoverPosition: 'left-0 md:right-0' })

  fireEvent.click(screen.getByLabelText('Filter'))

  expect(screen.queryByRole('dialog')).toBeNull()
  const group = screen.getByRole('button', { name: 'Course' })
  expect(group.closest('.absolute')).toHaveClass('left-0', 'md:right-0', 'z-10')
  fireEvent.click(screen.getByLabelText('Filter'))
  expect(screen.queryByRole('button', { name: 'Course' })).toBeNull()
})

test('the popover closes on Escape and on an outside click, not on a click inside', () => {
  stubViewport(false)
  renderControl()

  fireEvent.click(screen.getByLabelText('Filter'))
  fireEvent.mouseDown(screen.getByRole('button', { name: 'Course' }))
  expect(screen.getByRole('button', { name: 'Course' })).toBeInTheDocument()

  fireEvent.keyDown(document, { key: 'Escape' })
  expect(screen.queryByRole('button', { name: 'Course' })).toBeNull()

  fireEvent.click(screen.getByLabelText('Filter'))
  fireEvent.mouseDown(document.body)
  expect(screen.queryByRole('button', { name: 'Course' })).toBeNull()
})

test('on mobile it opens a sheet whose footer reports the result count and closes it', () => {
  stubViewport(true)
  renderControl({ resultCount: 1 })

  fireEvent.click(screen.getByLabelText('Filter'))

  const sheet = screen.getByRole('dialog', { name: 'Filters' })
  expect(within(sheet).getByRole('button', { name: 'Course' })).toBeInTheDocument()
  fireEvent.click(within(sheet).getByRole('button', { name: 'Show 1 recipe' }))
  expect(screen.queryByRole('dialog', { name: 'Filters' })).toBeNull()
})
