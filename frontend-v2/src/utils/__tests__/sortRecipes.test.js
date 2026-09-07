import { describe, expect, test } from 'vitest'
import { SORT_OPTIONS, defaultDirectionFor, sortRecipes } from '../sortRecipes'

const titlesOf = (recipes) => recipes.map((r) => r.title)

const RECIPES = [
  { title: 'Zuppa', course: 'first-course', score: 0.2 },
  { title: 'apple pie', course: 'dessert', score: null },
  { title: 'Burger', course: 'main', score: 0.9 },
  { title: 'Salad', course: 'side', score: 0.5 },
  { title: 'Anchovies', course: 'main', score: 0.1 },
]

test('exposes the four sort options', () => {
  expect(SORT_OPTIONS.map((o) => o.value)).toEqual(['default', 'score', 'name', 'course'])
})

test('default keeps the incoming order', () => {
  expect(titlesOf(sortRecipes(RECIPES, { key: 'default', direction: 'desc' }))).toEqual(
    titlesOf(RECIPES),
  )
})

test('does not mutate the input array', () => {
  const input = [...RECIPES]
  sortRecipes(input, { key: 'name', direction: 'asc' })
  expect(titlesOf(input)).toEqual(titlesOf(RECIPES))
})

describe('score', () => {
  test('descending puts the best first', () => {
    expect(titlesOf(sortRecipes(RECIPES, { key: 'score', direction: 'desc' }))).toEqual([
      'Burger',
      'Salad',
      'Zuppa',
      'Anchovies',
      'apple pie',
    ])
  })

  test('ascending puts the worst first but keeps unscored last', () => {
    expect(titlesOf(sortRecipes(RECIPES, { key: 'score', direction: 'asc' }))).toEqual([
      'Anchovies',
      'Zuppa',
      'Salad',
      'Burger',
      'apple pie',
    ])
  })
})

describe('name', () => {
  test('ascending is case-insensitive A→Z', () => {
    expect(titlesOf(sortRecipes(RECIPES, { key: 'name', direction: 'asc' }))).toEqual([
      'Anchovies',
      'apple pie',
      'Burger',
      'Salad',
      'Zuppa',
    ])
  })

  test('descending reverses it', () => {
    expect(titlesOf(sortRecipes(RECIPES, { key: 'name', direction: 'desc' }))).toEqual([
      'Zuppa',
      'Salad',
      'Burger',
      'apple pie',
      'Anchovies',
    ])
  })

  test('a missing title sorts as empty rather than throwing', () => {
    const sorted = sortRecipes([{ title: 'Burger' }, {}], { key: 'name', direction: 'asc' })
    expect(sorted[0].title).toBeUndefined()
  })
})

describe('course', () => {
  test('groups main, first-course, side, dessert with titles A→Z inside each', () => {
    expect(titlesOf(sortRecipes(RECIPES, { key: 'course', direction: 'asc' }))).toEqual([
      'Anchovies',
      'Burger',
      'Zuppa',
      'Salad',
      'apple pie',
    ])
  })

  test('descending reverses the groups but keeps titles A→Z inside each', () => {
    expect(titlesOf(sortRecipes(RECIPES, { key: 'course', direction: 'desc' }))).toEqual([
      'apple pie',
      'Salad',
      'Zuppa',
      'Anchovies',
      'Burger',
    ])
  })

  test('an unknown or missing course ranks after the known ones', () => {
    const sorted = sortRecipes(
      [{ title: 'Mystery', course: 'brunch' }, { title: 'Steak', course: 'main' }, { title: 'Nothing' }],
      { key: 'course', direction: 'asc' },
    )
    expect(titlesOf(sorted)).toEqual(['Steak', 'Mystery', 'Nothing'])
  })
})

describe('defaultDirectionFor', () => {
  test('score starts high→low, the others A→Z', () => {
    expect(defaultDirectionFor('score')).toBe('desc')
    expect(defaultDirectionFor('name')).toBe('asc')
    expect(defaultDirectionFor('course')).toBe('asc')
    expect(defaultDirectionFor('default')).toBe('asc')
  })
})
