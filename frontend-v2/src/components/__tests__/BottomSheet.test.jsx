/**
 * @vitest-environment jsdom
 */
import React from 'react'
import { render, screen, fireEvent, cleanup } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import '@testing-library/jest-dom/vitest'
import BottomSheet from '../BottomSheet'

afterEach(() => cleanup())

test('renders its title and children', () => {
  render(
    <BottomSheet title="Filters" onClose={() => {}}>
      <p>body</p>
    </BottomSheet>,
  )

  expect(screen.getByText('Filters')).toBeInTheDocument()
  expect(screen.getByText('body')).toBeInTheDocument()
})

test('Escape closes it', () => {
  const onClose = vi.fn()
  render(
    <BottomSheet title="Filters" onClose={onClose}>
      <p>body</p>
    </BottomSheet>,
  )

  fireEvent.keyDown(document, { key: 'Escape' })

  expect(onClose).toHaveBeenCalledTimes(1)
})

test('the close control is reachable by name', () => {
  const onClose = vi.fn()
  render(
    <BottomSheet title="Filters" onClose={onClose}>
      <p>body</p>
    </BottomSheet>,
  )

  fireEvent.click(screen.getByRole('button', { name: 'Close' }))

  expect(onClose).toHaveBeenCalledTimes(1)
})

test('a click inside the sheet does not close it', () => {
  const onClose = vi.fn()
  render(
    <BottomSheet title="Filters" onClose={onClose}>
      <p>body</p>
    </BottomSheet>,
  )

  fireEvent.click(screen.getByText('body'))

  expect(onClose).not.toHaveBeenCalled()
})

test('renders a footer when given one', () => {
  render(
    <BottomSheet title="Filters" onClose={() => {}} footer={<button type="button">Show 3</button>}>
      <p>body</p>
    </BottomSheet>,
  )

  expect(screen.getByRole('button', { name: 'Show 3' })).toBeInTheDocument()
})
