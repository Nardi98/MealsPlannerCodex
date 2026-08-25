import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { expect, test } from 'vitest'
import { STARTER_RECIPES, STARTER_GROUPS, groupStarterRecipes } from '../starterRecipes'

const here = path.dirname(fileURLToPath(import.meta.url))
const systemIngredients = JSON.parse(
  fs.readFileSync(
    path.resolve(here, '../../../../backend/data/system_ingredients.json'),
    'utf-8',
  ),
)

// Mirrors _PENALIZED_SYSTEM_TAGS + _NEUTRAL_SYSTEM_TAGS in
// backend/mealplanner/seed.py. A starter recipe may not invent a tag: the pack
// must be taggable with what every account is already seeded with.
const SYSTEM_TAGS = new Set([
  'pasta', 'soup', 'risotto', 'rice', 'pizza', 'salad', 'stew', 'roast',
  'sandwich', 'curry', 'noodles', 'gnocchi',
  'vegetarian', 'vegan', 'quick', 'cheap', 'spicy', 'gluten-free', 'breakfast',
])

const COURSES = new Set(['main', 'first-course', 'side'])
const UNITS = new Set(['g', 'kg', 'l', 'ml', 'piece'])

test('the pack holds 32 recipes with unique slugs and titles', () => {
  expect(STARTER_RECIPES).toHaveLength(32)
  expect(new Set(STARTER_RECIPES.map((r) => r.slug)).size).toBe(32)
  expect(new Set(STARTER_RECIPES.map((r) => r.title)).size).toBe(32)
})

test('every ingredient already exists in the seeded system library', () => {
  const known = new Set(systemIngredients.map((i) => i.name.toLowerCase()))
  const missing = []
  for (const recipe of STARTER_RECIPES) {
    for (const ing of recipe.ingredients) {
      if (!known.has(ing.name.toLowerCase())) missing.push(`${recipe.slug}: ${ing.name}`)
    }
  }
  expect(missing).toEqual([])
})

test('every tag is a seeded system tag', () => {
  const unknown = []
  for (const recipe of STARTER_RECIPES) {
    for (const tag of recipe.tags) {
      if (!SYSTEM_TAGS.has(tag)) unknown.push(`${recipe.slug}: ${tag}`)
    }
  }
  expect(unknown).toEqual([])
})

test('every entry is well formed', () => {
  for (const recipe of STARTER_RECIPES) {
    expect(COURSES.has(recipe.course), recipe.slug).toBe(true)
    expect(typeof recipe.bulk_prep).toBe('boolean')
    expect(recipe.minutes).toBeGreaterThan(0)
    expect(recipe.blurb.length).toBeGreaterThan(0)
    expect(recipe.procedure.length).toBeGreaterThan(0)
    expect(recipe.ingredients.length).toBeGreaterThan(1)
    for (const ing of recipe.ingredients) {
      expect(ing.quantity, `${recipe.slug}: ${ing.name}`).toBeGreaterThan(0)
      expect(UNITS.has(ing.unit), `${recipe.slug}: ${ing.unit}`).toBe(true)
    }
  }
})

test('quick is exactly the recipes that take 25 minutes or less', () => {
  for (const recipe of STARTER_RECIPES) {
    expect(recipe.tags.includes('quick'), recipe.slug).toBe(recipe.minutes <= 25)
  }
})

test('groupStarterRecipes buckets by format tag with Other last', () => {
  const groups = groupStarterRecipes(STARTER_RECIPES)
  const ordered = STARTER_GROUPS.map((g) => g.key).filter((k) => groups.some((g) => g.key === k))
  expect(groups.map((g) => g.key)).toEqual(ordered)
  expect(groups[groups.length - 1].key).toBe('other')
  // Every recipe lands in exactly one group.
  expect(groups.flatMap((g) => g.recipes)).toHaveLength(STARTER_RECIPES.length)
})
