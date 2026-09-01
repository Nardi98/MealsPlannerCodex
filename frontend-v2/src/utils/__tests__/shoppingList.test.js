import { describe, it, expect } from 'vitest'
import { buildShoppingList, batchLabel, formatExportText } from '../shoppingList'

// Each item is one recipe instance (a meal's main, or one of its sides) tagged
// with the number of people that meal is cooked for and the number the recipe
// itself was written for. Amounts are multiplied by `people / servings`; a
// recipe with no stated basis was written for one.
const item = (people, ingredients, servings = 1) => ({
  people,
  ingredients,
  servings,
})

// A recipe line as the API sends it: the line's own amount and unit, plus the
// ingredient's physics, so unification can happen here at read time.
const line = (name, amount, unit, physics = {}) => ({
  name,
  amount,
  unit,
  grams_per_ml: null,
  grams_per_piece: null,
  preferred_dimension: null,
  ...physics,
})

describe('buildShoppingList', () => {
  it('scales an ingredient amount by the meal people count', () => {
    const list = buildShoppingList([item(3, [line('Rice', 100, 'g')])])
    expect(list).toMatchObject([{ name: 'Rice', amount: 300, unit: 'g' }])
  })

  it('sums the same ingredient across occurrences at their own people counts', () => {
    const list = buildShoppingList([
      item(2, [line('Rice', 1000, 'g')]),
      item(4, [line('Rice', 1000, 'g')]),
    ])
    expect(list).toMatchObject([{ name: 'Rice', amount: 6000 }])
  })

  it('divides by the basis the recipe was authored for', () => {
    // A recipe written for 4 people, cooked for 2, needs half of everything.
    const list = buildShoppingList([item(2, [line('Pasta', 400, 'g')], 4)])
    expect(list).toMatchObject([{ name: 'Pasta', amount: 200, unit: 'g' }])
  })

  it('sums recipes written on different bases', () => {
    const list = buildShoppingList([
      item(2, [line('Rice', 400, 'g')], 4),
      item(2, [line('Rice', 100, 'g')], 1),
    ])
    expect(list).toMatchObject([{ name: 'Rice', amount: 400 }])
  })

  it('treats a missing or unusable basis as one serving', () => {
    const list = buildShoppingList([
      { people: 3, ingredients: [line('Egg', 1, 'piece')] },
      { people: 1, servings: 0, ingredients: [line('Egg', 1, 'piece')] },
    ])
    expect(list[0].amount).toBe(4)
  })

  it('rounds scaled amounts to 2 decimals', () => {
    const list = buildShoppingList([item(3, [line('Oil', 0.333, 'ml')])])
    expect(list[0].amount).toBe(1)
  })

  it('keeps a non-numeric amount as null', () => {
    const list = buildShoppingList([item(4, [line('Salt', '', '')])])
    expect(list[0].amount).toBeNull()
  })
})

// The whole point of the exercise: two recipes disagreeing about how to
// measure an onion is not two shopping list entries. It is one onion.
describe('unifying an ingredient measured two ways', () => {
  const onion = { grams_per_piece: 150 }

  it('merges mixed dimensions into a single row', () => {
    const list = buildShoppingList([
      item(1, [line('Onion', 2, 'piece', onion)]),
      item(1, [line('Onion', 200, 'g', onion)]),
    ])

    expect(list).toHaveLength(1)
    expect(list[0]).toMatchObject({ name: 'Onion', amount: 500, unit: 'g' })
  })

  it('offers every other reachable form as an alternate', () => {
    const list = buildShoppingList([
      item(1, [line('Onion', 2, 'piece', onion)]),
      item(1, [line('Onion', 200, 'g', onion)]),
    ])

    // 500 g is 3.33 onions, which rounds to the nearest quarter.
    expect(list[0].alternates).toEqual([{ amount: 3.25, unit: 'piece' }])
  })

  it('leads with the dimension the ingredient says it is measured in', () => {
    const counted = { grams_per_piece: 150, preferred_dimension: 'piece' }
    const list = buildShoppingList([
      item(1, [line('Onion', 2, 'piece', counted)]),
      item(1, [line('Onion', 300, 'g', counted)]),
    ])

    expect(list[0]).toMatchObject({ amount: 4, unit: 'piece' })
    expect(list[0].alternates).toEqual([{ amount: 600, unit: 'g' }])
  })

  it('falls back to the dimension most of the recipes used', () => {
    const list = buildShoppingList([
      item(1, [line('Onion', 1, 'piece', onion)]),
      item(1, [line('Onion', 1, 'piece', onion)]),
      item(1, [line('Onion', 100, 'g', onion)]),
    ])

    expect(list[0].unit).toBe('piece')
  })

  it('breaks a tie toward weighing it', () => {
    const list = buildShoppingList([
      item(1, [line('Onion', 1, 'piece', onion)]),
      item(1, [line('Onion', 100, 'g', onion)]),
    ])

    expect(list[0].unit).toBe('g')
  })

  it('ignores a stated preference the conversions cannot reach', () => {
    // Nothing knows what a millilitre of onion is, so the preference is moot
    // rather than an error, and the list quietly does the best it can.
    const unreachable = { grams_per_piece: 150, preferred_dimension: 'volume' }
    const list = buildShoppingList([
      item(1, [line('Onion', 2, 'piece', unreachable)]),
      item(1, [line('Onion', 200, 'g', unreachable)]),
    ])

    expect(list[0].unit).toBe('g')
    expect(list).toHaveLength(1)
  })
})

// A missing factor is not an error state. The list still works; it just says
// what it cannot do, at the exact moment the user has a reason to care.
describe('when a conversion is missing', () => {
  const split = () =>
    buildShoppingList([
      item(1, [line('Onion', 2, 'piece')]),
      item(1, [line('Onion', 200, 'g')]),
    ])

  it('splits into one row per dimension rather than guessing', () => {
    expect(split()).toMatchObject([
      { name: 'Onion', amount: 200, unit: 'g' },
      { name: 'Onion', amount: 2, unit: 'piece' },
    ])
  })

  it('flags each row with the factor that would unify them', () => {
    expect(split().every((r) => r.missing.includes('grams_per_piece'))).toBe(
      true,
    )
  })

  it('gives the split rows one identity, so they tick off together', () => {
    const [a, b] = split()
    expect(a.key).toBe(b.key)
    expect(a.rowKey).not.toBe(b.rowKey)
  })

  it('asks for a piece weight when a count and a volume disagree', () => {
    const list = buildShoppingList([
      item(1, [line('Milk', 1, 'piece')]),
      item(1, [line('Milk', 200, 'ml')]),
    ])
    expect(list[0].missing).toContain('grams_per_piece')
  })

  it('flags nothing at all when only one dimension is in play', () => {
    const list = buildShoppingList([item(1, [line('Salt', 5, 'g')])])
    expect(list[0].missing).toEqual([])
    expect(list[0].alternates).toEqual([])
  })
})

describe('ingredient identity', () => {
  it('merges on the ingredient id when the recipes name it differently', () => {
    const list = buildShoppingList([
      item(1, [{ ...line('Onion', 100, 'g'), id: 7 }]),
      item(1, [{ ...line('onions', 100, 'g'), id: 7 }]),
    ])
    expect(list).toHaveLength(1)
    expect(list[0].amount).toBe(200)
  })

  it('falls back to the name when no id is known', () => {
    const list = buildShoppingList([
      item(1, [line('Onion', 100, 'g')]),
      item(1, [line('onion', 100, 'g')]),
    ])
    expect(list).toHaveLength(1)
  })
})

describe('formatExportText', () => {
  const range = [new Date('2026-01-01'), new Date('2026-01-07')]

  it('renders the primary value only, a list and not a conversion table', () => {
    const list = buildShoppingList([
      item(1, [line('Onion', 2, 'piece', { grams_per_piece: 150 })]),
      item(1, [line('Onion', 200, 'g', { grams_per_piece: 150 })]),
    ])

    const text = formatExportText(list, ...range)
    expect(text).toContain('Onion: 500 g')
    expect(text).not.toContain('piece')
  })

  it('names an ingredient nobody stated an amount for', () => {
    const list = buildShoppingList([item(1, [line('Salt', '', '')])])
    expect(formatExportText(list, ...range)).toContain('Salt')
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
