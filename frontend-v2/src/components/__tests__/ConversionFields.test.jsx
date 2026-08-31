/** @vitest-environment jsdom */
import React from 'react'
import { render, screen, fireEvent, cleanup } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import '@testing-library/jest-dom/vitest'
import ConversionFields from '../ConversionFields'
import { toConversions, fromConversions } from '../../utils/conversionDraft'

afterEach(cleanup)

// The controlled shape the modals hold while the user is typing: what is in
// the boxes, not what will be stored.
const draft = (over = {}) => ({
  gramsPerPiece: '',
  gramsPer100Ml: '',
  preferredDimension: '',
  ...over,
})

function Harness({ initial = draft(), onChange = () => {} }) {
  const [value, setValue] = React.useState(initial)
  return (
    <ConversionFields
      value={value}
      onChange={(next) => {
        setValue(next)
        onChange(next)
      }}
    />
  )
}

test('asks for a piece weight in the words people use for it', () => {
  render(<Harness />)
  expect(screen.getByLabelText(/one piece weighs/i)).toBeInTheDocument()
})

test('asks for density per 100 ml, the scale people can estimate', () => {
  render(<Harness />)
  expect(screen.getByLabelText(/100 ml weighs/i)).toBeInTheDocument()
})

test('says plainly that leaving a field blank is a real answer', () => {
  render(<Harness />)
  expect(screen.getByText(/blank/i)).toBeInTheDocument()
})

test('both fields start empty and neither is required', () => {
  render(<Harness />)
  expect(screen.getByLabelText(/one piece weighs/i)).toHaveValue(null)
  expect(screen.getByLabelText(/one piece weighs/i)).not.toBeRequired()
  expect(screen.getByLabelText(/100 ml weighs/i)).not.toBeRequired()
})

test('offers only the dimensions the conversions actually reach', () => {
  // Filling in a piece weight is what unlocks counting this ingredient, and
  // the user gets to watch that happen.
  render(<Harness initial={draft({ gramsPerPiece: '150' })} />)

  const choices = [...screen.getByLabelText(/usually measured by/i).options].map(
    (o) => o.value,
  )
  expect(choices).toEqual(['', 'mass', 'piece'])
})

test('offers nothing but automatic when no conversion is stated', () => {
  render(<Harness />)
  const choices = [...screen.getByLabelText(/usually measured by/i).options].map(
    (o) => o.value,
  )
  expect(choices).toEqual([''])
})

test('reports what the user typed as they type it', () => {
  const onChange = vi.fn()
  render(<Harness onChange={onChange} />)

  fireEvent.change(screen.getByLabelText(/one piece weighs/i), {
    target: { value: '150' },
  })

  expect(onChange).toHaveBeenCalledWith(
    expect.objectContaining({ gramsPerPiece: '150' }),
  )
})

test('divides the density by a hundred on the way to storage', () => {
  expect(toConversions(draft({ gramsPer100Ml: '53' }))).toMatchObject({
    grams_per_ml: 0.53,
  })
})

test('multiplies it back by a hundred on the way to the form', () => {
  expect(fromConversions({ grams_per_ml: 0.53 })).toMatchObject({
    gramsPer100Ml: '53',
  })
})

test('stores a blank field as null rather than as a zero', () => {
  // Null is a permanent, legitimate answer: milk has no piece weight.
  expect(toConversions(draft({ gramsPer100Ml: '103' }))).toEqual({
    grams_per_ml: 1.03,
    grams_per_piece: null,
    preferred_dimension: null,
  })
})

test('round-trips an ingredient through the form without drift', () => {
  const stored = {
    grams_per_ml: 0.911,
    grams_per_piece: 227,
    preferred_dimension: 'mass',
  }
  expect(toConversions(fromConversions(stored))).toEqual(stored)
})
