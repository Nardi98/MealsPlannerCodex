import { describe, it, expect } from 'vitest'
import { learnedFacts, backfillFor } from '../importLearning'

// Every import teaches the pantry something, permanently and for free, and
// the user never fills in a form to make that happen. The receipt exists only
// so they can see it happening and catch an obviously wrong number.

describe('backfillFor', () => {
  it('offers a factor the ingredient does not have', () => {
    expect(
      backfillFor({ grams_per_piece: null }, { grams_per_piece: 150 }),
    ).toEqual({ grams_per_piece: 150 })
  })

  it('never overwrites a factor already stored', () => {
    // The database wins. The user may edit their number; an import may not.
    expect(
      backfillFor({ grams_per_piece: 140 }, { grams_per_piece: 150 }),
    ).toEqual({})
  })

  it('has nothing to offer when the reply omitted the factor', () => {
    expect(backfillFor({ grams_per_ml: null }, { grams_per_ml: null })).toEqual(
      {},
    )
  })

  it('teaches a brand new ingredient everything the reply supplied', () => {
    expect(
      backfillFor(null, { grams_per_ml: 0.53, grams_per_piece: null }),
    ).toEqual({ grams_per_ml: 0.53 })
  })
})

describe('learnedFacts', () => {
  it('reads a piece weight back in the words people use', () => {
    expect(learnedFacts([{ name: 'onion', grams_per_piece: 150 }])).toEqual([
      'onion ≈ 150 g each',
    ])
  })

  it('reads a density at the scale people can picture', () => {
    expect(learnedFacts([{ name: 'flour', grams_per_ml: 0.53 }])).toEqual([
      'flour ≈ 53 g per 100 ml',
    ])
  })

  it('says nothing about what the pantry already knew', () => {
    expect(learnedFacts([{ name: 'onion' }])).toEqual([])
  })

  it('reports both facts about one ingredient separately', () => {
    expect(
      learnedFacts([{ name: 'butter', grams_per_ml: 0.911, grams_per_piece: 227 }]),
    ).toEqual(['butter ≈ 227 g each', 'butter ≈ 91.1 g per 100 ml'])
  })
})
