import { describe, it, expect } from 'vitest'
import { buildShoppingList, batchLabel } from '../shoppingList'

// Each item is one recipe instance (a meal's main, or one of its sides) tagged
// with the number of people that meal is cooked for and the number the recipe
// itself was written for. Amounts are multiplied by `people / servings`; a
// recipe with no stated basis was written for one.
const item = (people, ingredients, servings = 1) => ({
  people,
  ingredients,
  servings,
})

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

  it('divides by the basis the recipe was authored for', () => {
    // A recipe written for 4 people, cooked for 2, needs half of everything.
    const list = buildShoppingList([
      item(2, [{ name: 'Pasta', amount: 400, unit: 'g' }], 4),
    ])
    expect(list).toEqual([
      { key: 'pasta||g', name: 'Pasta', amount: 200, unit: 'g' },
    ])
  })

  it('sums recipes written on different bases', () => {
    const list = buildShoppingList([
      item(2, [{ name: 'Rice', amount: 400, unit: 'g' }], 4),
      item(2, [{ name: 'Rice', amount: 100, unit: 'g' }], 1),
    ])
    expect(list).toEqual([
      { key: 'rice||g', name: 'Rice', amount: 400, unit: 'g' },
    ])
  })

  it('treats a missing or unusable basis as one serving', () => {
    const list = buildShoppingList([
      { people: 3, ingredients: [{ name: 'Egg', amount: 1, unit: 'piece' }] },
      { people: 1, servings: 0, ingredients: [{ name: 'Egg', amount: 1, unit: 'piece' }] },
    ])
    expect(list[0].amount).toBe(4)
  })
})

describe('batchLabel', () => {
  it('says nothing when the meal cooks the recipe exactly as written', () => {
    expect(batchLabel(4, 4)).toBeNull()
  })

  it('labels common fractions of a batch', () => {
    expect(batchLabel(2, 4)).toBe('×½')
    expect(batchLabel(1, 4)).toBe('×¼')
    expect(batchLabel(3, 4)).toBe('×¾')
    expect(batchLabel(6, 4)).toBe('×1½')
  })

  it('labels whole multiples without a fraction', () => {
    expect(batchLabel(8, 4)).toBe('×2')
  })

  it('labels a quarter over a whole batch', () => {
    expect(batchLabel(5, 4)).toBe('×1¼')
  })

  it('falls back to a rounded decimal for an awkward ratio', () => {
    expect(batchLabel(5, 3)).toBe('×1.67')
  })

  it('treats a missing basis as one serving', () => {
    expect(batchLabel(2)).toBe('×2')
  })
})
