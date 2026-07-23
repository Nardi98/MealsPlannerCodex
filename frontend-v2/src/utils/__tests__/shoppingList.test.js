import { describe, it, expect } from 'vitest'
import { buildShoppingList } from '../shoppingList'

// Each item is one recipe instance (a meal's main, or one of its sides) tagged
// with the number of people that meal is cooked for. Recipes are authored for
// one serving, so amounts are multiplied by `people`.
const item = (people, ingredients) => ({ people, ingredients })

describe('buildShoppingList', () => {
  it('scales an ingredient amount by the meal people count', () => {
    const list = buildShoppingList([
      item(3, [{ name: 'Rice', amount: 0.1, unit: 'kg' }]),
    ])
    expect(list).toEqual([
      { key: 'rice||kg', name: 'Rice', amount: 0.3, unit: 'kg' },
    ])
  })

  it('sums the same ingredient across occurrences at their own people counts', () => {
    const list = buildShoppingList([
      item(2, [{ name: 'Rice', amount: 1, unit: 'kg' }]),
      item(4, [{ name: 'Rice', amount: 1, unit: 'kg' }]),
    ])
    expect(list).toEqual([
      { key: 'rice||kg', name: 'Rice', amount: 6, unit: 'kg' },
    ])
  })

  it('folds side dishes at their parent meal people count', () => {
    const list = buildShoppingList([
      item(5, [{ name: 'Pasta', amount: 0.1, unit: 'kg' }]),
      item(5, [{ name: 'Salad', amount: 0.2, unit: 'kg' }]),
    ])
    expect(list).toContainEqual({
      key: 'salad||kg',
      name: 'Salad',
      amount: 1,
      unit: 'kg',
    })
  })

  it('rounds scaled amounts to 2 decimals', () => {
    const list = buildShoppingList([
      item(3, [{ name: 'Oil', amount: 0.333, unit: 'l' }]),
    ])
    expect(list[0].amount).toBe(1)
  })

  it('keeps a non-numeric amount as null', () => {
    const list = buildShoppingList([
      item(4, [{ name: 'Salt', amount: '', unit: '' }]),
    ])
    expect(list[0].amount).toBeNull()
  })
})
