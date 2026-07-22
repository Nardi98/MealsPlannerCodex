/**
 * @vitest-environment jsdom
 */
import { describe, expect, test } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import {
  buildGenerateParams,
  useGeneration,
  LEFTOVER_PRESETS,
  SEASONALITY_PRESETS,
  RECENCY_PRESETS,
} from '../useGeneration'

const baseForm = {
  start: '2024-01-01',
  end: '2024-01-07',
  meals_per_day: 2,
  epsilon: 0.25,
  leftovers: 'some',
  seasonality: 'prefer',
  recency: 'medium',
  avoid_tags: ['spicy'],
  reduce_tags: ['fish'],
}

describe('buildGenerateParams', () => {
  test('maps the default presets to backend weights', () => {
    const params = buildGenerateParams(baseForm)
    expect(params).toMatchObject({
      start: '2024-01-01',
      end: '2024-01-07',
      meals_per_day: 2,
      epsilon: 0.25,
      seasonality_weight: 1,
      recency_weight: 1,
      bulk_bonus_weight: 1,
      bulk_leftovers: true,
      keep_days: 3,
      avoid_tags: ['spicy'],
      reduce_tags: ['fish'],
    })
  })

  test('does not send a tag_penalty_weight (profile-driven now)', () => {
    expect(buildGenerateParams(baseForm)).not.toHaveProperty('tag_penalty_weight')
  })

  test('fresh leftovers preset disables leftovers and bulk bonus', () => {
    const params = buildGenerateParams({ ...baseForm, leftovers: 'fresh' })
    expect(params.bulk_leftovers).toBe(false)
    expect(params.bulk_bonus_weight).toBe(0)
    expect(params.keep_days).toBe(0)
  })

  test('lots leftovers preset boosts bulk bonus and keep days', () => {
    const params = buildGenerateParams({ ...baseForm, leftovers: 'lots' })
    expect(params.bulk_leftovers).toBe(true)
    expect(params.bulk_bonus_weight).toBe(2)
    expect(params.keep_days).toBe(5)
  })

  test('seasonality presets map to weights', () => {
    expect(buildGenerateParams({ ...baseForm, seasonality: 'ignore' }).seasonality_weight)
      .toBe(0)
    expect(buildGenerateParams({ ...baseForm, seasonality: 'strict' }).seasonality_weight)
      .toBe(3)
  })

  test('recency presets map to weights', () => {
    expect(buildGenerateParams({ ...baseForm, recency: 'low' }).recency_weight).toBe(0.5)
    expect(buildGenerateParams({ ...baseForm, recency: 'high' }).recency_weight).toBe(2)
  })

  test('preset tables expose the expected keys', () => {
    expect(Object.keys(LEFTOVER_PRESETS)).toEqual(['fresh', 'some', 'lots'])
    expect(Object.keys(SEASONALITY_PRESETS)).toEqual(['ignore', 'prefer', 'strict'])
    expect(Object.keys(RECENCY_PRESETS)).toEqual(['low', 'medium', 'high'])
  })
})

describe('useGeneration', () => {
  test('handleRangeChange updates both form.start and form.end', () => {
    const { result } = renderHook(() => useGeneration({ setPlan: () => {} }))
    act(() => {
      result.current.handleRangeChange({ start: '2024-03-04', end: '2024-03-10' })
    })
    expect(result.current.form.start).toBe('2024-03-04')
    expect(result.current.form.end).toBe('2024-03-10')
  })
})
