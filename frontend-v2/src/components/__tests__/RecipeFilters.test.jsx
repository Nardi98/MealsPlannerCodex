/**
 * @vitest-environment jsdom
 */
import { render, screen, fireEvent, cleanup } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import '@testing-library/jest-dom/vitest'
import RecipeFilters from '../RecipeFilters'

afterEach(() => cleanup())

const ingredients = ['Tomato', 'Tofu', 'Anchovy']

function group(overrides = {}) {
  return {
    label: 'Ingredients',
    options: ingredients,
    selected: [],
    onSelect: () => {},
    ...overrides,
  }
}

function expand(label = 'Ingredients') {
  fireEvent.click(screen.getByRole('button', { name: new RegExp(`^${label}`) }))
}

test('a group opens to show its options as chips', () => {
  render(<RecipeFilters groups={[group({ label: 'Course', options: ['main', 'side'] })]} />)
  expand('Course')

  expect(screen.getByRole('button', { name: 'main' })).toBeInTheDocument()
})

test('a chip reports the option it stands for', () => {
  const onSelect = vi.fn()
  render(<RecipeFilters groups={[group({ label: 'Course', options: ['main'], onSelect })]} />)
  expand('Course')

  fireEvent.click(screen.getByRole('button', { name: 'main' }))

  expect(onSelect).toHaveBeenCalledWith('main')
})

// A searchable group is for a list long enough that showing all of it is the
// problem. An account's whole ingredient catalogue is exactly that.
test('a searchable group shows no options until something is typed', () => {
  render(<RecipeFilters groups={[group({ searchable: true })]} />)
  expand()

  expect(screen.queryByRole('button', { name: 'Tomato' })).not.toBeInTheDocument()
  expect(screen.getByPlaceholderText('Search Ingredients…')).toBeInTheDocument()
})

test('typing narrows the options to what matches, case-insensitively', () => {
  render(<RecipeFilters groups={[group({ searchable: true })]} />)
  expand()

  fireEvent.change(screen.getByPlaceholderText('Search Ingredients…'), {
    target: { value: 'to' },
  })

  expect(screen.getByRole('button', { name: 'Tomato' })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Tofu' })).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Anchovy' })).not.toBeInTheDocument()
})

// Otherwise a filter you have switched on becomes unreachable from the sheet
// that switched it on: nothing is listed until you type, and you would have to
// guess the name of what you already picked to turn it off again.
test('a selected option stays listed whatever the query is', () => {
  render(<RecipeFilters groups={[group({ searchable: true, selected: ['Anchovy'] })]} />)
  expand()
  expect(screen.getByRole('button', { name: 'Anchovy' })).toBeInTheDocument()

  fireEvent.change(screen.getByPlaceholderText('Search Ingredients…'), {
    target: { value: 'tom' },
  })

  expect(screen.getByRole('button', { name: 'Anchovy' })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Tomato' })).toBeInTheDocument()
})

test('a match that is already selected is not listed a second time', () => {
  render(<RecipeFilters groups={[group({ searchable: true, selected: ['Tomato'] })]} />)
  expand()

  fireEvent.change(screen.getByPlaceholderText('Search Ingredients…'), {
    target: { value: 'tom' },
  })

  expect(screen.getAllByRole('button', { name: 'Tomato' })).toHaveLength(1)
})

test('closing the group forgets the query', () => {
  render(<RecipeFilters groups={[group({ searchable: true })]} />)
  expand()
  fireEvent.change(screen.getByPlaceholderText('Search Ingredients…'), {
    target: { value: 'tom' },
  })

  expand()
  expand()

  expect(screen.getByPlaceholderText('Search Ingredients…')).toHaveValue('')
  expect(screen.queryByRole('button', { name: 'Tomato' })).not.toBeInTheDocument()
})

test('an unsearchable group still shows everything at once', () => {
  render(<RecipeFilters groups={[group({ label: 'Tags', options: ['quick', 'vegan'] })]} />)
  expand('Tags')

  expect(screen.getByRole('button', { name: 'quick' })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'vegan' })).toBeInTheDocument()
  expect(screen.queryByPlaceholderText(/Search/)).not.toBeInTheDocument()
})
