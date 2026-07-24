/**
 * @vitest-environment jsdom
 */
import { render, screen, fireEvent, cleanup } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import '@testing-library/jest-dom/vitest'
import FridgeSelector from '../FridgeSelector'

afterEach(() => {
  cleanup()
})

const ingredients = [
  { id: 1, name: 'Onion', unit: 'pcs' },
  { id: 2, name: 'Tomato', unit: 'pcs' },
]

const renderSelector = (props = {}) =>
  render(
    <FridgeSelector
      ingredients={ingredients}
      value={[]}
      onChange={() => {}}
      {...props}
    />
  )

test('picking an ingredient adds it with a count of 1', () => {
  const onChange = vi.fn()
  renderSelector({ onChange })
  fireEvent.change(screen.getByPlaceholderText(/search ingredients/i), {
    target: { value: 'onion' },
  })
  fireEvent.click(screen.getByRole('button', { name: /onion/i }))
  expect(onChange).toHaveBeenCalledWith([{ ingredient_id: 1, count: 1 }])
})

test('renders selected ingredients as chips showing the count', () => {
  renderSelector({ value: [{ ingredient_id: 2, count: 3 }] })
  expect(screen.getByText('Tomato')).toBeInTheDocument()
  expect(screen.getByText('3')).toBeInTheDocument()
})

test('increment raises the count for that ingredient', () => {
  const onChange = vi.fn()
  renderSelector({ value: [{ ingredient_id: 1, count: 1 }], onChange })
  fireEvent.click(screen.getByRole('button', { name: /increase onion/i }))
  expect(onChange).toHaveBeenCalledWith([{ ingredient_id: 1, count: 2 }])
})

test('decrement below 1 removes the ingredient', () => {
  const onChange = vi.fn()
  renderSelector({ value: [{ ingredient_id: 1, count: 1 }], onChange })
  fireEvent.click(screen.getByRole('button', { name: /decrease onion/i }))
  expect(onChange).toHaveBeenCalledWith([])
})

test('picking an already-selected ingredient does not duplicate it', () => {
  const onChange = vi.fn()
  renderSelector({ value: [{ ingredient_id: 1, count: 1 }], onChange })
  fireEvent.change(screen.getByPlaceholderText(/search ingredients/i), {
    target: { value: 'onion' },
  })
  fireEvent.click(screen.getByRole('button', { name: /^onion/i }))
  expect(onChange).not.toHaveBeenCalled()
})
