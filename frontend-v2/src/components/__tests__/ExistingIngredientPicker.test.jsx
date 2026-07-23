/**
 * @vitest-environment jsdom
 */
import React from 'react'
import { render, screen, fireEvent, cleanup } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import '@testing-library/jest-dom/vitest'
import ExistingIngredientPicker from '../ExistingIngredientPicker'

afterEach(cleanup)

const options = [
  { id: 1, name: 'Basil', unit: 'g' },
  { id: 2, name: 'Bay leaf', unit: 'piece' },
  { id: 3, name: 'Carrot', unit: 'g' },
]
const suggestions = [{ id: 1, name: 'Basil', unit: 'g' }]

test('surfaces suggestions and selects one', () => {
  const onChange = vi.fn()
  render(
    <ExistingIngredientPicker
      value=""
      options={options}
      suggestions={suggestions}
      onChange={onChange}
    />
  )
  expect(screen.getByText(/suggested/i)).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: /basil/i }))
  expect(onChange).toHaveBeenCalledWith(1)
})

test('searches the full list when suggestions miss', () => {
  const onChange = vi.fn()
  render(
    <ExistingIngredientPicker
      value=""
      options={options}
      suggestions={suggestions}
      onChange={onChange}
    />
  )
  fireEvent.change(screen.getByPlaceholderText(/search ingredients/i), {
    target: { value: 'carr' },
  })
  fireEvent.click(screen.getByRole('button', { name: /carrot/i }))
  expect(onChange).toHaveBeenCalledWith(3)
})

test('highlights the button of the selected ingredient', () => {
  render(
    <ExistingIngredientPicker
      value={1}
      options={options}
      suggestions={suggestions}
      onChange={() => {}}
    />
  )
  expect(screen.getByRole('button', { name: /basil/i })).toHaveAttribute(
    'aria-pressed',
    'true'
  )
})

test('shows the currently selected ingredient name', () => {
  render(
    <ExistingIngredientPicker
      value={3}
      options={options}
      suggestions={[]}
      onChange={() => {}}
    />
  )
  expect(screen.getByText(/selected:\s*carrot/i)).toBeInTheDocument()
})
