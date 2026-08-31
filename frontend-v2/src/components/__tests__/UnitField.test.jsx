/** @vitest-environment jsdom */
import React from 'react'
import { render, screen, fireEvent, cleanup } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import '@testing-library/jest-dom/vitest'
import UnitField from '../UnitField'

afterEach(cleanup)

function Harness({ amount = '', unit = 'g', system, onChange = () => {} }) {
  const [value, setValue] = React.useState({ amount, unit })
  return (
    <UnitField
      amount={value.amount}
      unit={value.unit}
      system={system}
      onChange={(next) => {
        setValue(next)
        onChange(next)
      }}
    />
  )
}

test('offers what people actually write, not just what is stored', () => {
  render(<Harness />)
  const offered = [...screen.getByLabelText(/unit/i).options].map((o) => o.value)

  expect(offered).toContain('cup')
  expect(offered).toContain('tbsp')
  expect(offered).toContain('lb')
  expect(offered).toContain('clove')
})

test('leads with the units this reader writes in', () => {
  render(<Harness system="us" />)
  const offered = [...screen.getByLabelText(/unit/i).options].map((o) => o.value)
  expect(offered[0]).toBe('oz')
})

test('echoes the converted value as the user types it', () => {
  // Nothing is silently rewritten underneath them: they watch the conversion
  // happen and can correct the unit before saving.
  render(<Harness amount="1" unit="cup" />)
  expect(screen.getByText(/236.6 ml/)).toBeInTheDocument()
})

test('says nothing when the unit is already the stored one', () => {
  render(<Harness amount="250" unit="g" />)
  expect(screen.queryByText(/=/)).toBeNull()
})

test('says nothing until there is an amount to convert', () => {
  render(<Harness amount="" unit="cup" />)
  expect(screen.queryByText(/=/)).toBeNull()
})

test('reports the amount and unit as entered, not as converted', () => {
  // The parent normalises on save, so the field stays honest about what is in
  // the boxes while the user is still editing them.
  const onChange = vi.fn()
  render(<Harness amount="1" unit="g" onChange={onChange} />)

  fireEvent.change(screen.getByLabelText(/unit/i), { target: { value: 'cup' } })

  expect(onChange).toHaveBeenCalledWith({ amount: '1', unit: 'cup' })
})
