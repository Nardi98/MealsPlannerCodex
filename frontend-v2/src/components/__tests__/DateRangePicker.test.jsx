/**
 * @vitest-environment jsdom
 */
import { render, screen, fireEvent, cleanup, within } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import '@testing-library/jest-dom/vitest'
import DateRangePicker from '../DateRangePicker'

afterEach(() => {
  cleanup()
})

test('shows the placeholder when no range is selected', () => {
  render(<DateRangePicker start="" end="" onChange={() => {}} placeholder="Pick dates" />)
  expect(screen.getByRole('button', { name: /pick dates/i })).toBeInTheDocument()
})

test('shows the formatted range and inclusive day count when set', () => {
  render(<DateRangePicker start="2024-01-01" end="2024-01-07" onChange={() => {}} />)
  const trigger = screen.getByRole('button', { name: /jan/i })
  expect(trigger).toHaveTextContent('1 Jan')
  expect(trigger).toHaveTextContent('7 Jan')
  expect(trigger).toHaveTextContent('7 days')
})

test('opens the calendar on trigger click and closes via the close icon', () => {
  render(<DateRangePicker start="2024-01-01" end="2024-01-07" onChange={() => {}} />)
  expect(screen.queryByRole('grid')).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: /jan/i }))
  expect(screen.getByRole('grid')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: /close/i }))
  expect(screen.queryByRole('grid')).not.toBeInTheDocument()
})

test('closes on outside click', () => {
  render(
    <div>
      <span data-testid="outside">outside</span>
      <DateRangePicker start="2024-01-01" end="2024-01-07" onChange={() => {}} />
    </div>
  )
  fireEvent.click(screen.getByRole('button', { name: /jan/i }))
  expect(screen.getByRole('grid')).toBeInTheDocument()
  fireEvent.mouseDown(screen.getByTestId('outside'))
  expect(screen.queryByRole('grid')).not.toBeInTheDocument()
})

test('picking a start then an end day calls onChange with the range', () => {
  const onChange = vi.fn()
  render(<DateRangePicker start="2024-01-01" end="2024-01-07" onChange={onChange} />)
  fireEvent.click(screen.getByRole('button', { name: /jan/i }))
  const grid = screen.getByRole('grid')
  fireEvent.click(within(grid).getByRole('button', { name: /January 10(?!\d)/ }))
  fireEvent.click(within(grid).getByRole('button', { name: /January 15(?!\d)/ }))
  expect(onChange).toHaveBeenLastCalledWith({ start: '2024-01-10', end: '2024-01-15' })
})

test('normalizes an earlier second pick so start precedes end', () => {
  const onChange = vi.fn()
  render(<DateRangePicker start="2024-01-01" end="2024-01-07" onChange={onChange} />)
  fireEvent.click(screen.getByRole('button', { name: /jan/i }))
  const grid = screen.getByRole('grid')
  fireEvent.click(within(grid).getByRole('button', { name: /January 20(?!\d)/ }))
  fireEvent.click(within(grid).getByRole('button', { name: /January 12(?!\d)/ }))
  const last = onChange.mock.calls.at(-1)[0]
  expect(new Date(last.start) <= new Date(last.end)).toBe(true)
  expect(last).toEqual({ start: '2024-01-12', end: '2024-01-20' })
})
