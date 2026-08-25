/**
 * @vitest-environment jsdom
 */
import { renderHook, act } from '@testing-library/react'
import { afterEach, beforeEach, expect, test } from 'vitest'
import { useTour } from '../useTour'
import { isTourDone, markTourDone } from '../tourStorage'

const STEPS = [
  { target: '[data-tour="a"]', title: 'A', body: 'first' },
  { target: '[data-tour="b"]', title: 'B', body: 'second' },
]

function anchor(name, box) {
  const el = document.createElement('div')
  el.setAttribute('data-tour', name)
  el.getBoundingClientRect = () => ({ top: 10, left: 20, width: 100, height: 40, bottom: 50, right: 120, ...box })
  document.body.appendChild(el)
  return el
}

beforeEach(() => {
  localStorage.clear()
})

afterEach(() => {
  document.body.innerHTML = ''
})

test('auto-starts on the first step when the tour has never been completed', () => {
  anchor('a')
  const { result } = renderHook(() => useTour({ id: 'recipes', steps: STEPS }))
  expect(result.current.running).toBe(true)
  expect(result.current.index).toBe(0)
  expect(result.current.total).toBe(2)
  expect(result.current.step.title).toBe('A')
})

test('does not auto-start once the tour is marked done', () => {
  markTourDone('recipes')
  const { result } = renderHook(() => useTour({ id: 'recipes', steps: STEPS }))
  expect(result.current.running).toBe(false)
})

test('does not auto-start while disabled, and starts when it becomes enabled', () => {
  const { result, rerender } = renderHook(({ enabled }) => useTour({ id: 'recipes', steps: STEPS, enabled }), {
    initialProps: { enabled: false },
  })
  expect(result.current.running).toBe(false)
  rerender({ enabled: true })
  expect(result.current.running).toBe(true)
})

test('next advances, and finishing the last step closes and records the tour', () => {
  const { result } = renderHook(() => useTour({ id: 'recipes', steps: STEPS }))
  act(() => result.current.next())
  expect(result.current.index).toBe(1)
  expect(result.current.isLast).toBe(true)
  act(() => result.current.next())
  expect(result.current.running).toBe(false)
  expect(isTourDone('recipes')).toBe(true)
})

test('back steps toward the start and stops there', () => {
  const { result } = renderHook(() => useTour({ id: 'recipes', steps: STEPS }))
  act(() => result.current.next())
  act(() => result.current.back())
  expect(result.current.index).toBe(0)
  act(() => result.current.back())
  expect(result.current.index).toBe(0)
})

test('skip closes the tour and silences every page', () => {
  const { result } = renderHook(() => useTour({ id: 'recipes', steps: STEPS }))
  act(() => result.current.skip())
  expect(result.current.running).toBe(false)
  expect(isTourDone('recipes')).toBe(true)
  expect(isTourDone('meal-plan')).toBe(true)
  expect(isTourDone('ingredients')).toBe(true)
})

test('a present target yields its rect; a missing one yields null', () => {
  anchor('a')
  const { result } = renderHook(() => useTour({ id: 'recipes', steps: STEPS }))
  expect(result.current.rect).toMatchObject({ top: 10, left: 20, width: 100, height: 40 })
  act(() => result.current.next())
  expect(result.current.rect).toBe(null)
})

test('a missing target does not change the step count', () => {
  const { result } = renderHook(() => useTour({ id: 'recipes', steps: STEPS }))
  expect(result.current.total).toBe(2)
  expect(result.current.rect).toBe(null)
})

test('start replays a completed tour from the beginning', () => {
  markTourDone('recipes')
  const { result } = renderHook(() => useTour({ id: 'recipes', steps: STEPS }))
  act(() => result.current.start())
  expect(result.current.running).toBe(true)
  expect(result.current.index).toBe(0)
})
