import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { expect, test } from 'vitest'
import { STARTER_RECIPES, groupStarterRecipes } from '../starterRecipes'
import { COURSES, UNITS } from '../recipeImport'

const here = path.dirname(fileURLToPath(import.meta.url))
const systemIngredients = JSON.parse(
  fs.readFileSync(
    path.resolve(here, '../../../../backend/data/system_ingredients.json'),
    'utf-8',
  ),
)

// The tag vocabulary is read from the backend data file rather than mirrored
// here, the same way the ingredient library is above: a starter recipe may not
// invent a tag, and this check must fail when the two drift.
const SYSTEM_TAGS = new Set(
  JSON.parse(
    fs.readFileSync(path.resolve(here, '../../../../backend/data/system_tags.json'), 'utf-8'),
  ).map((tag) => tag.name),
)

test('the pack holds 60 recipes with unique slugs and titles', () => {
  expect(STARTER_RECIPES).toHaveLength(60)
  expect(new Set(STARTER_RECIPES.map((r) => r.slug)).size).toBe(60)
  expect(new Set(STARTER_RECIPES.map((r) => r.title)).size).toBe(60)
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
    expect(COURSES, recipe.slug).toContain(recipe.course)
    expect(typeof recipe.bulk_prep).toBe('boolean')
    expect(recipe.minutes).toBeGreaterThan(0)
    expect(recipe.blurb.length).toBeGreaterThan(0)
    expect(recipe.procedure.length).toBeGreaterThan(0)
    expect(recipe.ingredients.length).toBeGreaterThan(1)
    for (const ing of recipe.ingredients) {
      expect(ing.quantity, `${recipe.slug}: ${ing.name}`).toBeGreaterThan(0)
      expect(UNITS, `${recipe.slug}: ${ing.unit}`).toContain(ing.unit)
    }
  }
})

test('a stated head-count is a whole number of people', () => {
  // Omitting `servings` means "written for one person"; stating it must mean
  // something the shopping list can divide by.
  for (const recipe of STARTER_RECIPES) {
    if (recipe.servings === undefined) continue
    expect(Number.isInteger(recipe.servings), recipe.slug).toBe(true)
    expect(recipe.servings, recipe.slug).toBeGreaterThanOrEqual(1)
  }
})

test('no quantity asks the cook to measure a fraction of a countable thing', () => {
  // A piece is a whole object. Half an egg is the awkwardness the servings
  // basis exists to avoid, so a recipe needing one is written for more people.
  for (const recipe of STARTER_RECIPES) {
    for (const ing of recipe.ingredients) {
      if (ing.unit !== 'piece') continue
      expect(Number.isInteger(ing.quantity), `${recipe.slug}: ${ing.name}`).toBe(true)
    }
  }
})

test('quick is exactly the recipes that take 25 minutes or less', () => {
  for (const recipe of STARTER_RECIPES) {
    expect(recipe.tags.includes('quick'), recipe.slug).toBe(recipe.minutes <= 25)
  }
})

test('groupStarterRecipes sections by course, format tags ordering within', () => {
  const recipe = (slug, course, tags) => ({ slug, course, tags })
  const groups = groupStarterRecipes([
    recipe('a-side', 'side', ['salad']),
    recipe('a-soup', 'first-course', ['soup']),
    recipe('a-plain-main', 'main', []),
    recipe('a-pasta', 'first-course', ['pasta']),
    recipe('a-stew', 'main', ['stew']),
  ])

  expect(groups.map((g) => g.key)).toEqual(['first-course', 'main', 'side'])
  expect(groups.map((g) => g.label)).toEqual(['First courses', 'Mains', 'Sides'])
  // pasta precedes soup in the format order; a recipe with no format tag sorts last.
  expect(groups[0].recipes.map((r) => r.slug)).toEqual(['a-pasta', 'a-soup'])
  expect(groups[1].recipes.map((r) => r.slug)).toEqual(['a-stew', 'a-plain-main'])
  expect(groups[2].recipes.map((r) => r.slug)).toEqual(['a-side'])
})

test('groupStarterRecipes skips empty sections and keeps every recipe once', () => {
  const groups = groupStarterRecipes(STARTER_RECIPES)
  expect(groups.flatMap((g) => g.recipes)).toHaveLength(STARTER_RECIPES.length)

  const onlySides = groupStarterRecipes([{ slug: 's', course: 'side', tags: [] }])
  expect(onlySides.map((g) => g.key)).toEqual(['side'])
})

test('the pack offers every course, with enough sides to plan from', () => {
  const byCourse = (course) => STARTER_RECIPES.filter((r) => r.course === course)
  expect(byCourse('side').length).toBeGreaterThanOrEqual(10)
  expect(byCourse('main').length).toBeGreaterThan(0)
  expect(byCourse('first-course').length).toBeGreaterThan(0)
})
