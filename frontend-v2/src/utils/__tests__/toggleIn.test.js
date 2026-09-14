import { expect, test } from 'vitest'
import { toggleIn } from '../toggleIn'

test('adds a missing value at the end', () => {
  expect(toggleIn(['a'], 'b')).toEqual(['a', 'b'])
})

test('removes a present value', () => {
  expect(toggleIn(['a', 'b', 'c'], 'b')).toEqual(['a', 'c'])
})

test('never mutates the list it was given', () => {
  const list = ['a']
  toggleIn(list, 'b')
  toggleIn(list, 'a')
  expect(list).toEqual(['a'])
})
