/**
 * @vitest-environment jsdom
 */
import { render, screen, fireEvent, cleanup } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import '@testing-library/jest-dom/vitest'
import SegmentedControl from '../SegmentedControl'

const OPTIONS = [
  { value: 'a', label: 'Everything', sub: 'fresh' },
  { value: 'b', label: 'Some', sub: 'leftovers' },
  { value: 'c', label: 'Cook', sub: 'in bulk' },
]

afterEach(() => {
  cleanup()
})

test('renders the label and every option as a tab', () => {
  render(
    <SegmentedControl label="Leftovers" options={OPTIONS} value="a" onChange={() => {}} />
  )
  expect(screen.getByText('Leftovers')).toBeInTheDocument()
  expect(screen.getByRole('tab', { name: 'Everything fresh' })).toBeInTheDocument()
  expect(screen.getByRole('tab', { name: 'Some leftovers' })).toBeInTheDocument()
  expect(screen.getByRole('tab', { name: 'Cook in bulk' })).toBeInTheDocument()
})

test('marks the selected option as selected', () => {
  render(
    <SegmentedControl label="Leftovers" options={OPTIONS} value="b" onChange={() => {}} />
  )
  expect(screen.getByRole('tab', { name: 'Some leftovers' })).toHaveAttribute(
    'aria-selected',
    'true'
  )
  expect(screen.getByRole('tab', { name: 'Everything fresh' })).toHaveAttribute(
    'aria-selected',
    'false'
  )
})

test('slides the bar to the selected index', () => {
  const { container } = render(
    <SegmentedControl label="Leftovers" options={OPTIONS} value="c" onChange={() => {}} />
  )
  const bar = container.querySelector('.segu-bar')
  expect(bar).toHaveStyle({ transform: 'translateX(calc(2 * (100% + 4px)))' })
})

test('calls onChange with the clicked option value', () => {
  const onChange = vi.fn()
  render(
    <SegmentedControl label="Leftovers" options={OPTIONS} value="a" onChange={onChange} />
  )
  fireEvent.click(screen.getByRole('tab', { name: 'Cook in bulk' }))
  expect(onChange).toHaveBeenCalledWith('c')
})

test('arrow keys move the selection', () => {
  const onChange = vi.fn()
  render(
    <SegmentedControl label="Leftovers" options={OPTIONS} value="a" onChange={onChange} />
  )
  fireEvent.keyDown(screen.getByRole('tab', { name: 'Everything fresh' }), {
    key: 'ArrowRight',
  })
  expect(onChange).toHaveBeenCalledWith('b')
})
