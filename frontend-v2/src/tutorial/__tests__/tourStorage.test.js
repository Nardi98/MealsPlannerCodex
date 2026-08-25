/**
 * @vitest-environment jsdom
 */
import { beforeEach, expect, test } from 'vitest'
import { TOUR_IDS, isTourDone, markTourDone, markAllToursDone } from '../tourStorage'

beforeEach(() => {
  localStorage.clear()
})

test('a tour is not done until it is marked', () => {
  expect(isTourDone('recipes')).toBe(false)
  markTourDone('recipes')
  expect(isTourDone('recipes')).toBe(true)
})

test('marking one tour leaves the others untouched', () => {
  markTourDone('recipes')
  expect(isTourDone('meal-plan')).toBe(false)
})

test('skipping marks every known tour done', () => {
  markAllToursDone()
  for (const id of TOUR_IDS) expect(isTourDone(id)).toBe(true)
})

test('every tour in the registry is one skipping can silence', () => {
  expect(TOUR_IDS).toContain('recipes')
  expect(TOUR_IDS).toContain('meal-plan')
  expect(TOUR_IDS).toContain('ingredients')
})

test('reads and writes survive storage throwing', () => {
  const original = Object.getOwnPropertyDescriptor(window, 'localStorage')
  Object.defineProperty(window, 'localStorage', {
    configurable: true,
    get() {
      throw new Error('blocked')
    },
  })
  expect(() => markTourDone('recipes')).not.toThrow()
  expect(isTourDone('recipes')).toBe(false)
  Object.defineProperty(window, 'localStorage', original)
})
