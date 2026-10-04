import { expect, test } from 'vitest'
import { shownDate } from '../formatDate'

test('formats a date as day, short month and year in the reader’s locale', () => {
  const iso = '2026-09-04T10:00:00'
  expect(shownDate(iso)).toBe(
    new Date(iso).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' }),
  )
})

test('a missing date shows nothing', () => {
  expect(shownDate(null)).toBe('')
  expect(shownDate(undefined)).toBe('')
  expect(shownDate('')).toBe('')
})

test('an unparseable value is shown as it came', () => {
  expect(shownDate('someday')).toBe('someday')
})
