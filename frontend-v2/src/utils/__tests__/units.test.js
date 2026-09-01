import { describe, it, expect } from 'vitest'
import {
  BASE_UNITS,
  UNIT_OPTIONS,
  dimensionOf,
  toBaseUnit,
  fromBaseUnit,
  convert,
  reachableDimensions,
  roundPieces,
  formatAmount,
  alternateForms,
  missingFactorsFor,
} from '../units'

// The vocabulary the app accepts at its edges. Storage only ever holds the
// three base units; everything else is a way of writing one of them down.
describe('the unit vocabulary', () => {
  it('bases exactly one unit on each dimension', () => {
    expect(BASE_UNITS).toEqual({ mass: 'g', volume: 'ml', piece: 'piece' })
  })

  it('offers the curated entry vocabulary metric-first by default', () => {
    expect(UNIT_OPTIONS('metric')).toEqual([
      'g', 'kg', 'ml', 'l', 'piece',
      'oz', 'lb', 'tsp', 'tbsp', 'cup', 'fl oz', 'clove', 'slice',
    ])
  })

  it('leads with the US units when the user reads in US', () => {
    expect(UNIT_OPTIONS('us').slice(0, 6)).toEqual([
      'oz', 'lb', 'cup', 'tbsp', 'tsp', 'fl oz',
    ])
  })

  it('places every accepted unit in a dimension', () => {
    for (const unit of UNIT_OPTIONS('metric')) {
      expect(dimensionOf(unit)).not.toBeNull()
    }
  })

  it('has no dimension for a unit it does not know', () => {
    expect(dimensionOf('bag')).toBeNull()
  })
})

describe('toBaseUnit', () => {
  it('leaves a base unit alone', () => {
    expect(toBaseUnit(250, 'g')).toEqual({ amount: 250, unit: 'g' })
  })

  it.each([
    [1, 'kg', 1000, 'g'],
    [1, 'oz', 28.35, 'g'],
    [1, 'lb', 453.6, 'g'],
    [1, 'l', 1000, 'ml'],
    [1, 'cup', 236.6, 'ml'],
    [1, 'tbsp', 14.8, 'ml'],
    [1, 'tsp', 4.93, 'ml'],
    [1, 'fl oz', 29.57, 'ml'],
  ])('converts %s %s to %s %s', (amount, unit, expected, expectedUnit) => {
    expect(toBaseUnit(amount, unit)).toEqual({
      amount: expected,
      unit: expectedUnit,
    })
  })

  // Count-ish words are how a source writes a piece. The chatbot's
  // grams_per_piece is then per clove, which is what we want.
  it.each(['clove', 'slice', 'bunch'])('normalises %s to a piece', (unit) => {
    expect(toBaseUnit(3, unit)).toEqual({ amount: 3, unit: 'piece' })
  })

  it('scales the factor by the amount', () => {
    expect(toBaseUnit(2, 'cup')).toEqual({ amount: 473.2, unit: 'ml' })
  })

  it('refuses a unit outside the vocabulary rather than guessing', () => {
    expect(toBaseUnit(1, 'bag')).toBeNull()
  })

  it('carries a null amount through without inventing one', () => {
    expect(toBaseUnit(null, 'cup')).toEqual({ amount: null, unit: 'ml' })
  })
})

describe('fromBaseUnit', () => {
  it.each([
    [1000, 'g', 'kg', 1],
    [28.35, 'g', 'oz', 1],
    [236.6, 'ml', 'cup', 1],
    [1000, 'ml', 'l', 1],
  ])('renders %s %s as %s %s', (amount, base, unit, expected) => {
    expect(fromBaseUnit(amount, unit)).toBeCloseTo(expected, 10)
  })

  // Round-tripping is the property that makes the table trustworthy.
  it.each(['kg', 'oz', 'lb', 'l', 'cup', 'tbsp', 'tsp', 'fl oz'])(
    'round-trips %s through its base unit',
    (unit) => {
      const { amount } = toBaseUnit(7, unit)
      expect(fromBaseUnit(amount, unit)).toBeCloseTo(7, 10)
    },
  )

  it('refuses a unit outside the vocabulary', () => {
    expect(fromBaseUnit(100, 'bag')).toBeNull()
  })
})

// Tier 2: crossing a dimension needs the ingredient's own physics. A null
// factor is a recorded fact -- "this ingredient has no meaningful volume" --
// and the converter refuses to cross it rather than inventing a number.
const flour = { grams_per_ml: 0.53, grams_per_piece: null }
const onion = { grams_per_ml: null, grams_per_piece: 150 }
const butter = { grams_per_ml: 0.911, grams_per_piece: 227 }
const unknown = { grams_per_ml: null, grams_per_piece: null }

describe('convert', () => {
  it('leaves an amount alone within one dimension', () => {
    expect(convert(250, 'mass', 'mass', unknown)).toBe(250)
  })

  it('weighs a volume with the density', () => {
    expect(convert(100, 'volume', 'mass', flour)).toBeCloseTo(53, 10)
  })

  it('measures a weight as a volume with the density', () => {
    expect(convert(53, 'mass', 'volume', flour)).toBeCloseTo(100, 10)
  })

  it('weighs a count with the piece weight', () => {
    expect(convert(2, 'piece', 'mass', onion)).toBeCloseTo(300, 10)
  })

  it('counts a weight with the piece weight', () => {
    expect(convert(300, 'mass', 'piece', onion)).toBeCloseTo(2, 10)
  })

  // Volume to count is two hops, and needs both factors.
  it('crosses volume to count through mass', () => {
    expect(convert(227, 'volume', 'piece', butter)).toBeCloseTo(0.911, 10)
  })

  it('crosses count to volume through mass', () => {
    expect(convert(1, 'piece', 'volume', butter)).toBeCloseTo(227 / 0.911, 10)
  })

  it.each([
    ['volume', 'mass', onion],
    ['mass', 'volume', onion],
    ['piece', 'mass', flour],
    ['mass', 'piece', flour],
    ['volume', 'piece', flour],
    ['piece', 'volume', flour],
    ['volume', 'piece', onion],
    ['piece', 'volume', onion],
    ['volume', 'mass', unknown],
    ['piece', 'mass', unknown],
  ])('refuses %s to %s when the factor is null', (from, to, ingredient) => {
    expect(convert(10, from, to, ingredient)).toBeNull()
  })

  it('refuses a null amount rather than inventing one', () => {
    expect(convert(null, 'volume', 'mass', flour)).toBeNull()
  })

  it('refuses an ingredient it was given nothing about', () => {
    expect(convert(10, 'volume', 'mass', null)).toBeNull()
  })

  // A zero factor is not a factor. Dividing by it would produce Infinity.
  it('refuses a zero factor rather than dividing by it', () => {
    expect(convert(10, 'mass', 'piece', { grams_per_piece: 0 })).toBeNull()
  })
})

describe('reachableDimensions', () => {
  it('reaches every dimension when both factors are known', () => {
    expect(reachableDimensions(butter)).toEqual(['mass', 'volume', 'piece'])
  })

  it('reaches mass and volume from a density alone', () => {
    expect(reachableDimensions(flour)).toEqual(['mass', 'volume'])
  })

  it('reaches mass and piece from a piece weight alone', () => {
    expect(reachableDimensions(onion)).toEqual(['mass', 'piece'])
  })

  // Nothing is broken about an ingredient nobody has taught us anything about.
  it('reaches nothing on its own for an ingredient with no factors', () => {
    expect(reachableDimensions(unknown)).toEqual([])
  })
})

// Pieces round to a quarter and never to zero: a recipe needing *some* onion
// means buying one, and rounding it away would be worse than rounding it up.
describe('roundPieces', () => {
  it.each([
    [2, 2],
    [1.6, 1.5],
    [1.4, 1.5],
    [0.3, 0.25],
    [0.9, 1],
  ])('rounds %s pieces to %s', (amount, expected) => {
    expect(roundPieces(amount)).toBe(expected)
  })

  it('floors at a quarter rather than rounding a real need away', () => {
    expect(roundPieces(0.05)).toBe(0.25)
  })

  it('leaves a genuine zero alone', () => {
    expect(roundPieces(0)).toBe(0)
  })
})

describe('formatAmount', () => {
  it('renders grams as grams below the promotion boundary', () => {
    expect(formatAmount(250, 'g', 'metric')).toBe('250 g')
  })

  it('promotes to kg at exactly a thousand grams', () => {
    expect(formatAmount(1000, 'g', 'metric')).toBe('1 kg')
  })

  it('stays in grams one gram below the boundary', () => {
    expect(formatAmount(999, 'g', 'metric')).toBe('999 g')
  })

  it('promotes to litres above a thousand millilitres', () => {
    expect(formatAmount(1200, 'ml', 'metric')).toBe('1.2 l')
  })

  it('rounds a metric amount to two decimals', () => {
    expect(formatAmount(33.333, 'g', 'metric')).toBe('33.33 g')
  })

  it('renders a small mass in ounces for a US reader', () => {
    expect(formatAmount(56.7, 'g', 'us')).toBe('2 oz')
  })

  it('promotes to pounds at a pound for a US reader', () => {
    expect(formatAmount(907.2, 'g', 'us')).toBe('2 lb')
  })

  it('renders a small volume in fluid ounces for a US reader', () => {
    expect(formatAmount(29.57, 'ml', 'us')).toBe('1 fl oz')
  })

  it('promotes to cups at a cup for a US reader', () => {
    expect(formatAmount(473.2, 'ml', 'us')).toBe('2 cup')
  })

  // Pieces are counted, not measured, so the system does not touch them.
  it('counts pieces the same way in both systems', () => {
    expect(formatAmount(2, 'piece', 'metric')).toBe('2 piece')
    expect(formatAmount(2, 'piece', 'us')).toBe('2 piece')
  })

  it('spells a fractional count with the shared fraction glyphs', () => {
    expect(formatAmount(1.5, 'piece', 'metric')).toBe('1½ piece')
    expect(formatAmount(0.25, 'piece', 'metric')).toBe('¼ piece')
  })

  it('has nothing to render for an amount nobody stated', () => {
    expect(formatAmount(null, 'g', 'metric')).toBeNull()
  })
})

// One helper for "every other way this amount could be written", shared by
// the recipe page and the shopping list so the two cannot drift apart.
describe('alternateForms', () => {
  it('offers the weight of a counted amount', () => {
    expect(alternateForms(2, 'piece', onion)).toEqual([
      { amount: 300, unit: 'g' },
    ])
  })

  it('offers every form a fully known ingredient reaches', () => {
    expect(alternateForms(227, 'g', butter)).toEqual([
      { amount: 249.18, unit: 'ml' },
      { amount: 1, unit: 'piece' },
    ])
  })

  it('rounds a counted alternate to a quarter', () => {
    expect(alternateForms(500, 'g', onion)).toEqual([
      { amount: 3.25, unit: 'piece' },
    ])
  })

  it('offers nothing for an ingredient nobody has taught us about', () => {
    expect(alternateForms(5, 'g', unknown)).toEqual([])
  })

  it('offers nothing when there is no amount to restate', () => {
    expect(alternateForms(null, 'g', onion)).toEqual([])
  })
})

// The dimension topology lives beside `convert`, which is what defines it.
describe('missingFactorsFor', () => {
  it('asks for a piece weight to reconcile a count with a weight', () => {
    expect(missingFactorsFor(['mass', 'piece'], unknown)).toEqual([
      'grams_per_piece',
    ])
  })

  it('asks for a density to reconcile a volume with a weight', () => {
    expect(missingFactorsFor(['mass', 'volume'], unknown)).toEqual([
      'grams_per_ml',
    ])
  })

  it('asks for both to reconcile a count with a volume', () => {
    expect(missingFactorsFor(['volume', 'piece'], unknown)).toEqual([
      'grams_per_ml',
      'grams_per_piece',
    ])
  })

  it('asks only for what is actually absent', () => {
    expect(missingFactorsFor(['mass', 'volume', 'piece'], flour)).toEqual([
      'grams_per_piece',
    ])
  })

  it('asks for nothing when one dimension is all that is in play', () => {
    expect(missingFactorsFor(['mass'], unknown)).toEqual([])
  })

  it('ignores a dimension it does not recognise', () => {
    expect(missingFactorsFor(['mass', ''], unknown)).toEqual([])
  })
})

// The quarter floor exists so a recipe needing *some* onion means buying one.
// It must not invent a quantity out of one that was never positive: a negative
// amount is bad data, and rendering it as ¼ hides the very thing that would
// let someone notice.
describe('roundPieces on amounts that are not positive', () => {
  it('does not turn a negative amount into a quarter', () => {
    expect(roundPieces(-18)).toBe(-18)
  })

  it('leaves a genuine zero alone', () => {
    expect(roundPieces(0)).toBe(0)
  })

  it('still floors a real but tiny need at a quarter', () => {
    expect(roundPieces(0.05)).toBe(0.25)
  })

  it('has no count to give for something that is not a number', () => {
    expect(roundPieces(NaN)).toBeNull()
  })
})
