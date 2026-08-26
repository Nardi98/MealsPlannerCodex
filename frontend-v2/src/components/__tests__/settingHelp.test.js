import { expect, test } from 'vitest'
import { SETTING_HELP } from '../settingHelp'
import { LEFTOVER_PRESETS, SEASONALITY_PRESETS, RECENCY_PRESETS } from '../../hooks/useGeneration'

// Every control on the Meal Plan form, by the key the form looks it up under.
const KEYS = [
  'dates',
  'meals_per_day',
  'epsilon',
  'leftovers',
  'seasonality',
  'recency',
  'avoid_tags',
  'reduce_tags',
  'fridge',
]

test('every setting on the form has help text', () => {
  expect(Object.keys(SETTING_HELP).sort()).toEqual([...KEYS].sort())
})

test.each(KEYS)('%s has a title and a body worth reading', (key) => {
  const help = SETTING_HELP[key]
  expect(help.title.length).toBeGreaterThan(0)
  expect(help.body.length).toBeGreaterThan(30)
})

// The point of the tooltip is explaining the presets, so the ones that have
// presets must document every one of them — a preset added to the form without
// a line here would ship unexplained.
test.each([
  ['leftovers', Object.keys(LEFTOVER_PRESETS)],
  ['seasonality', Object.keys(SEASONALITY_PRESETS)],
  ['recency', Object.keys(RECENCY_PRESETS)],
])('%s explains each of its presets', (key, presets) => {
  const listed = SETTING_HELP[key].presets
  expect(listed.map((p) => p.value)).toEqual(presets)
  listed.forEach((p) => {
    expect(p.label.length).toBeGreaterThan(0)
    expect(p.text.length).toBeGreaterThan(10)
  })
})

test('meals per day explains both of its choices', () => {
  expect(SETTING_HELP.meals_per_day.presets.map((p) => p.value)).toEqual([1, 2])
})

test('settings without presets do not invent any', () => {
  ;['dates', 'epsilon', 'avoid_tags', 'reduce_tags', 'fridge'].forEach((key) => {
    expect(SETTING_HELP[key].presets).toBeUndefined()
  })
})
