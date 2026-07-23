import { describe, expect, test } from 'vitest'
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
    expect(IMPORT_PROMPT).toMatch(/single serving/i)
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
      { id: undefined, name: 'Basil', amount: 50, unit: 'g', season_months: [5, 6, 7, 8] },
      { id: undefined, name: 'Pasta', amount: 100, unit: 'g', season_months: [] },
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
