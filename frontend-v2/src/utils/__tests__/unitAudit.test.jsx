/**
 * Audit probes for the measurement-unit branch.
 *
 * Each test states the behaviour the design document asks for. A failure here
 * is a bug in the branch, not in the test.
 */
/** @vitest-environment jsdom */
import React from 'react'
import { afterEach, describe, it, expect } from 'vitest'
import { render, screen, fireEvent, cleanup } from '@testing-library/react'
import '@testing-library/jest-dom/vitest'

import { alternateForms, formatAmount } from '../units'
import { buildShoppingList } from '../shoppingList'
import ConversionFields from '../../components/ConversionFields'
import Quantity from '../../components/Quantity'

afterEach(cleanup)

// --- 1. the recipe page's call to alternateForms ---------------------------

describe('the recipe page shows every alternate form', () => {
  // RecipesPage renders `alternateForms(ing)` -- one argument, where the
  // module takes (amount, unit, ingredient).
  const line = { amount: 200, unit: 'g', grams_per_piece: 100 }

  it('offers a count beside a weight the ingredient can be counted in', () => {
    expect(alternateForms(line)).toEqual([{ amount: 2, unit: 'piece' }])
  })

  it('is what the three-argument call already returns', () => {
    expect(alternateForms(line.amount, line.unit, line)).toEqual([
      { amount: 2, unit: 'piece' },
    ])
  })
})

// --- 2. a quantity with no unit ---------------------------------------------

describe('an amount whose line states no unit', () => {
  // `IngredientOut.unit` is Optional and `import_data` writes null units, so
  // this is real stored data, not a hypothetical.
  it('formats rather than throwing', () => {
    expect(() => formatAmount(2, null)).not.toThrow()
  })

  it('does not take the recipe page down with it', () => {
    expect(() =>
      render(<Quantity amount={2} unit={null} alternates={[]} system="metric" />),
    ).not.toThrow()
  })
})

// --- 3. a unit outside the vocabulary --------------------------------------

describe('an ingredient line written in an unrecognised unit', () => {
  const listWith = (rows) =>
    buildShoppingList([{ people: 1, servings: 1, ingredients: rows }])

  it('is never restated as a count it never claimed to be', () => {
    // 100 g at 10 g a piece is 10 pieces. The 5 "bogus" must not be added to
    // a converted 10 and served up as 15 of nothing.
    const rows = listWith([
      { id: 1, name: 'x', amount: 5, unit: 'bogus', grams_per_piece: 10 },
      { id: 1, name: 'x', amount: 100, unit: 'g', grams_per_piece: 10 },
    ])
    expect(rows.map((r) => [r.amount, r.unit])).not.toContainEqual([15, ''])
  })

  it('is not dropped from the list when the entry splits', () => {
    const rows = listWith([
      { id: 1, name: 'x', amount: 5, unit: 'bogus' },
      { id: 1, name: 'x', amount: 100, unit: 'g' },
      { id: 1, name: 'x', amount: 2, unit: 'piece' },
    ])
    const total = rows.reduce((n, r) => n + (r.amount ?? 0), 0)
    expect(total).toBe(107)
  })
})

// --- 4. clearing a factor must retire the preference it unlocked -----------

describe('the ingredient editor after a factor is cleared', () => {
  function Harness() {
    const [value, setValue] = React.useState({
      gramsPerPiece: '150',
      gramsPer100Ml: '',
      preferredDimension: 'piece',
    })
    return (
      <>
        <ConversionFields value={value} onChange={setValue} />
        <output data-testid="draft">{value.preferredDimension}</output>
      </>
    )
  }

  it('does not keep preferring a dimension nothing can reach', () => {
    render(<Harness />)
    expect(screen.getByLabelText('Usually measured by')).toHaveValue('piece')

    fireEvent.change(screen.getByLabelText('One piece weighs'), {
      target: { value: '' },
    })

    // The select now shows "Automatic" because `piece` is no longer an option.
    expect(screen.getByLabelText('Usually measured by')).toHaveValue('')
    // The draft that gets saved must agree with what the user is looking at.
    expect(screen.getByTestId('draft')).toBeEmptyDOMElement()
  })
})
