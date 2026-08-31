/** @vitest-environment jsdom */
import { render, screen, cleanup } from '@testing-library/react'
import { afterEach, expect, test } from 'vitest'
import '@testing-library/jest-dom/vitest'
import Quantity from '../Quantity'

afterEach(cleanup)

test('renders the amount in the base unit it was stored in', () => {
  render(<Quantity amount={250} unit="g" />)
  expect(screen.getByText('250 g')).toBeInTheDocument()
})

test('promotes a large amount rather than printing every zero', () => {
  render(<Quantity amount={1200} unit="g" />)
  expect(screen.getByText('1.2 kg')).toBeInTheDocument()
})

test('renders the same stored amount in US units for a US reader', () => {
  // Display only: the number handed in is the stored one either way.
  render(<Quantity amount={907.2} unit="g" system="us" />)
  expect(screen.getByText('2 lb')).toBeInTheDocument()
})

test('shows every alternate form beside the primary one', () => {
  render(
    <Quantity amount={500} unit="g" alternates={[{ amount: 3.25, unit: 'piece' }]} />,
  )
  expect(screen.getByText('500 g')).toBeInTheDocument()
  expect(screen.getByText(/3¼ piece/)).toBeInTheDocument()
})

test('renders nothing for an ingredient nobody stated an amount for', () => {
  const { container } = render(<Quantity amount={null} unit="g" />)
  expect(container).toBeEmptyDOMElement()
})

test('mutes the alternate so the primary value reads first', () => {
  render(
    <Quantity amount={500} unit="g" alternates={[{ amount: 3.25, unit: 'piece' }]} />,
  )
  // The design guide's existing subtle token, not a new colour.
  expect(screen.getByText(/3¼ piece/)).toHaveStyle({
    color: 'var(--text-subtle)',
  })
})
