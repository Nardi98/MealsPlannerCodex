import { describe, expect, it, test } from 'vitest'
import { IMPORT_PROMPT, parseImportedRecipe } from '../recipeImport'

const validPayload = {
  title: 'Pasta al Pesto',
  course: 'main',
  procedure: 'Boil pasta, mix with pesto.',
  bulk_prep: true,
  tags: ['quick', 'vegetarian'],
  ingredients: [
    { name: 'Basil', quantity: 50, unit: 'g', season_months: [5, 6, 7, 8] },
    { name: 'Pasta', quantity: 100, unit: 'g' },
  ],
}

describe('IMPORT_PROMPT', () => {
  test('documents the accepted courses and units for the chatbot', () => {
    expect(IMPORT_PROMPT).toContain('first-course')
    expect(IMPORT_PROMPT).toContain('piece')
    expect(IMPORT_PROMPT).toMatch(/EXACTLY as the recipe states it/i)
  })
})

describe('parseImportedRecipe', () => {
  test('maps a valid payload to the internal recipe shape', () => {
    const { recipe, errors } = parseImportedRecipe(JSON.stringify(validPayload))

    expect(errors).toEqual([])
    expect(recipe).toMatchObject({
      title: 'Pasta al Pesto',
      course: 'main',
      procedure: 'Boil pasta, mix with pesto.',
      hot: true,
      image_url: null,
      tags: ['quick', 'vegetarian'],
      favorite_side_ids: [],
    })
    expect(recipe.ingredients).toEqual([
      {
        id: undefined,
        name: 'Basil',
        amount: 50,
        unit: 'g',
        season_months: [5, 6, 7, 8],
        grams_per_ml: null,
        grams_per_piece: null,
      },
      {
        id: undefined,
        name: 'Pasta',
        amount: 100,
        unit: 'g',
        season_months: [],
        grams_per_ml: null,
        grams_per_piece: null,
      },
    ])
  })

  test('defaults optional fields when omitted', () => {
    const { recipe, errors } = parseImportedRecipe(
      JSON.stringify({ title: 'Plain', course: 'side', ingredients: [] })
    )
    expect(errors).toEqual([])
    expect(recipe).toMatchObject({
      procedure: '',
      hot: false,
      tags: [],
      ingredients: [],
    })
  })

  test('reports malformed JSON', () => {
    const { recipe, errors } = parseImportedRecipe('{ not json')
    expect(recipe).toBeNull()
    expect(errors.join(' ')).toMatch(/valid json/i)
  })

  test('requires a non-empty title', () => {
    const { recipe, errors } = parseImportedRecipe(
      JSON.stringify({ ...validPayload, title: '  ' })
    )
    expect(recipe).toBeNull()
    expect(errors.join(' ')).toMatch(/title/i)
  })

  test('rejects an unknown course', () => {
    const { errors } = parseImportedRecipe(
      JSON.stringify({ ...validPayload, course: 'dessert' })
    )
    expect(errors.join(' ')).toMatch(/course/i)
  })

  test('rejects an unknown ingredient unit', () => {
    const { errors } = parseImportedRecipe(
      JSON.stringify({
        ...validPayload,
        ingredients: [{ name: 'Basil', quantity: 50, unit: 'cups' }],
      })
    )
    expect(errors.join(' ')).toMatch(/unit/i)
  })

  test('rejects a non-numeric ingredient quantity', () => {
    const { errors } = parseImportedRecipe(
      JSON.stringify({
        ...validPayload,
        ingredients: [{ name: 'Basil', quantity: 'a lot', unit: 'g' }],
      })
    )
    expect(errors.join(' ')).toMatch(/quantity/i)
  })

  test('rejects an ingredient without a name', () => {
    const { errors } = parseImportedRecipe(
      JSON.stringify({
        ...validPayload,
        ingredients: [{ quantity: 50, unit: 'g' }],
      })
    )
    expect(errors.join(' ')).toMatch(/name/i)
  })
})


// --- the servings basis -----------------------------------------------------

test('the prompt asks for quantities as written, with their head-count', () => {
  // Asking a chatbot to divide a recipe by its serving count is exactly the
  // fraction-mangling the servings basis exists to avoid.
  expect(IMPORT_PROMPT).not.toMatch(/SINGLE serving/i)
  expect(IMPORT_PROMPT).toMatch(/"servings"/)
})

test('parses the servings basis the chatbot reported', () => {
  const { recipe, errors } = parseImportedRecipe(
    JSON.stringify({
      title: 'Ribollita',
      course: 'main',
      servings: 4,
      ingredients: [{ name: 'Cavolo nero', quantity: 800, unit: 'g' }],
    }),
  )
  expect(errors).toEqual([])
  expect(recipe.servings).toBe(4)
  // Quantities arrive as written; nothing is divided down.
  expect(recipe.ingredients[0].amount).toBe(800)
})

test('a missing or unusable servings basis means one person', () => {
  const one = parseImportedRecipe(
    JSON.stringify({
      title: 'Toast',
      course: 'main',
      ingredients: [{ name: 'Bread', quantity: 1, unit: 'piece' }],
    }),
  )
  expect(one.recipe.servings).toBe(1)

  const junk = parseImportedRecipe(
    JSON.stringify({
      title: 'Toast',
      course: 'main',
      servings: 0,
      ingredients: [{ name: 'Bread', quantity: 1, unit: 'piece' }],
    }),
  )
  expect(junk.recipe.servings).toBe(1)
})


// --- the chatbot reporting failure ------------------------------------------

test('the prompt asks for a plain sentence rather than an invented recipe', () => {
  expect(IMPORT_PROMPT).toMatch(/plain/i)
  expect(IMPORT_PROMPT).toMatch(/do NOT\s+invent one/i)
})

test('surfaces the plain-text reason the chatbot could not read a recipe', () => {
  const { recipe, errors } = parseImportedRecipe(
    'That page is a login wall, not a recipe.',
  )
  expect(recipe).toBeNull()
  expect(errors).toEqual(['That page is a login wall, not a recipe.'])
})

test('an empty reply reports a failure of its own', () => {
  const { recipe, errors } = parseImportedRecipe('   ')
  expect(recipe).toBeNull()
  expect(errors).toEqual(['Pasted text is not valid JSON.'])
})

test('a long reply is trimmed to something the modal can show', () => {
  const { errors } = parseImportedRecipe('x'.repeat(500))
  expect(errors[0].length).toBeLessThanOrEqual(300)
  expect(errors[0]).toMatch(/…$/)
})

test('a mangled JSON reply still reads as JSON trouble, not a reason', () => {
  // A reply that was meant to be the object -- a stray markdown fence, a
  // truncated brace -- is a formatting slip, not the chatbot explaining itself.
  const { errors } = parseImportedRecipe('{"title": "Toast",')
  expect(errors).toEqual(['Pasted text is not valid JSON.'])
})

test('an "error" key in a valid object is not treated as a failure', () => {
  const { recipe, errors } = parseImportedRecipe(
    JSON.stringify({
      error: 'ignored',
      title: 'Toast',
      course: 'main',
      ingredients: [{ name: 'Bread', quantity: 1, unit: 'piece' }],
    }),
  )
  expect(errors).toEqual([])
  expect(recipe.title).toBe('Toast')
})

// The prompt stops asking the chatbot to convert or to match a pantry it
// cannot see, and asks only for physical facts, which are the same for
// everyone. The app -- the only party that knows the pantry -- does the rest.
describe('importing physical facts rather than conversions', () => {
  const reply = (ingredient) =>
    JSON.stringify({
      title: 'Soffritto',
      course: 'main',
      procedure: 'Chop.',
      servings: 2,
      tags: [],
      ingredients: [ingredient],
    })

  it('accepts the units people actually write', () => {
    const { recipe, errors } = parseImportedRecipe(
      reply({ name: 'flour', quantity: 1, unit: 'cup', grams_per_ml: 0.53 }),
    )
    expect(errors).toEqual([])
    expect(recipe.ingredients[0]).toMatchObject({ amount: 236.6, unit: 'ml' })
  })

  it('normalises a count-ish word to a piece', () => {
    // The piece weight is then per clove, which is what we want.
    const { recipe } = parseImportedRecipe(
      reply({ name: 'garlic', quantity: 3, unit: 'clove', grams_per_piece: 5 }),
    )
    expect(recipe.ingredients[0]).toMatchObject({ amount: 3, unit: 'piece' })
    expect(recipe.ingredients[0].grams_per_piece).toBe(5)
  })

  it('carries the conversions through for the app to back-fill', () => {
    const { recipe } = parseImportedRecipe(
      reply({ name: 'onion', quantity: 2, unit: 'piece', grams_per_piece: 150 }),
    )
    expect(recipe.ingredients[0]).toMatchObject({
      grams_per_piece: 150,
      grams_per_ml: null,
    })
  })

  it('treats an omitted conversion as a valid answer, not an error', () => {
    // Omitting one means "this dimension does not apply to this ingredient".
    const { recipe, errors } = parseImportedRecipe(
      reply({ name: 'egg', quantity: 2, unit: 'piece' }),
    )
    expect(errors).toEqual([])
    expect(recipe.ingredients[0].grams_per_ml).toBeNull()
  })

  it('still refuses a unit nobody measures anything in', () => {
    const { errors } = parseImportedRecipe(
      reply({ name: 'rice', quantity: 1, unit: 'bag' }),
    )
    expect(errors.join(' ')).toMatch(/unit/i)
  })

  it('ignores a conversion that is not a positive number', () => {
    const { recipe, errors } = parseImportedRecipe(
      reply({ name: 'onion', quantity: 2, unit: 'piece', grams_per_piece: 0 }),
    )
    expect(errors).toEqual([])
    expect(recipe.ingredients[0].grams_per_piece).toBeNull()
  })

  it('asks the chatbot for facts, not for a conversion into my units', () => {
    expect(IMPORT_PROMPT).toMatch(/grams_per_piece/)
    expect(IMPORT_PROMPT).toMatch(/grams_per_ml/)
    expect(IMPORT_PROMPT).not.toMatch(/must be one of: g, kg, l, ml, piece/)
  })
})
