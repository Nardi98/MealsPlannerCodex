/**
 * @vitest-environment jsdom
 */
import React from 'react'
import { render, screen, fireEvent, cleanup } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import '@testing-library/jest-dom/vitest'
import FavoriteSidesSelect from '../FavoriteSidesSelect'

afterEach(cleanup)

const OPTIONS = [
  { id: 7, title: 'Mashed Potatoes' },
  { id: 8, title: 'Steamed Broccoli' },
  { id: 9, title: 'Greek Salad' },
]

const setup = (props = {}) => {
  const onChange = vi.fn()
  render(
    <FavoriteSidesSelect
      options={OPTIONS}
      selected={[]}
      onChange={onChange}
      {...props}
    />
  )
  return onChange
}

const openMenu = () => fireEvent.click(screen.getByRole('button', { name: /add a side/i }))

test('the option list is hidden until the menu is opened', () => {
  setup()
  expect(screen.queryByText('Mashed Potatoes')).toBeNull()

  openMenu()

  expect(screen.getByText('Mashed Potatoes')).toBeInTheDocument()
})

test('the search bar filters the options', () => {
  setup()
  openMenu()

  fireEvent.change(screen.getByPlaceholderText(/search/i), {
    target: { value: 'broc' },
  })

  expect(screen.getByText('Steamed Broccoli')).toBeInTheDocument()
  expect(screen.queryByText('Mashed Potatoes')).toBeNull()
})

test('searching is case insensitive', () => {
  setup()
  openMenu()

  fireEvent.change(screen.getByPlaceholderText(/search/i), {
    target: { value: 'GREEK' },
  })

  expect(screen.getByText('Greek Salad')).toBeInTheDocument()
})

test('clicking an option adds it', () => {
  const onChange = setup()
  openMenu()

  fireEvent.click(screen.getByText('Steamed Broccoli'))

  expect(onChange).toHaveBeenCalledWith([8])
})

test('a selected side shows up as a chip', () => {
  setup({ selected: [8] })

  expect(screen.getByTestId('favorite-side-chip-8')).toHaveTextContent(
    'Steamed Broccoli'
  )
})

test('an already selected side is not offered again in the menu', () => {
  setup({ selected: [8] })
  openMenu()

  // The chip still shows it, but the menu must not offer a duplicate.
  expect(screen.queryByRole('option', { name: 'Steamed Broccoli' })).toBeNull()
  expect(screen.getByRole('option', { name: 'Mashed Potatoes' })).toBeInTheDocument()
})

test('removing a chip deselects that side', () => {
  const onChange = setup({ selected: [7, 8] })

  fireEvent.click(screen.getByRole('button', { name: /remove mashed potatoes/i }))

  expect(onChange).toHaveBeenCalledWith([8])
})

test('tells the user when there are no sides to choose from', () => {
  setup({ options: [] })
  openMenu()

  expect(screen.getByText(/no side dishes/i)).toBeInTheDocument()
})

test('says so when the search matches nothing', () => {
  setup()
  openMenu()

  fireEvent.change(screen.getByPlaceholderText(/search/i), {
    target: { value: 'zzz' },
  })

  expect(screen.getByText(/no match/i)).toBeInTheDocument()
})

test('shows a hint instead of chips when nothing is selected', () => {
  setup()

  expect(screen.getByText(/no favorite sides yet/i)).toBeInTheDocument()
})
