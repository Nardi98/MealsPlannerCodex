import React from 'react'
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react'
import { vi, afterEach, test, expect } from 'vitest'
import RecipeForm from '../RecipeForm'
import { recipesApi } from '../../api'

afterEach(() => {
  vi.restoreAllMocks()
  cleanup()
})

test('course selector defaults to main', () => {
  render(<RecipeForm />)
  const select = screen.getByLabelText(/course/i)
  expect(select.value).toBe('main')
})

test('submitting recipe sends selected course', async () => {
  const createMock = vi
    .spyOn(recipesApi, 'create')
    .mockResolvedValue({ course: 'dessert' })
  render(<RecipeForm />)
  fireEvent.change(screen.getByLabelText(/title/i), { target: { value: 'Pie' } })
  fireEvent.change(screen.getByLabelText(/servings/i), { target: { value: '4' } })
  fireEvent.change(screen.getByLabelText(/course/i), { target: { value: 'dessert' } })
  fireEvent.click(screen.getByText('Save'))
  await waitFor(() => expect(createMock).toHaveBeenCalled())
  expect(createMock.mock.calls[0][0].course).toBe('dessert')
})

test('ingredient without season defaults to all months', async () => {
  const createMock = vi.spyOn(recipesApi, 'create').mockResolvedValue({})
  render(<RecipeForm />)
  fireEvent.change(screen.getByLabelText(/title/i), { target: { value: 'Soup' } })
  fireEvent.change(screen.getByLabelText(/servings/i), { target: { value: '2' } })
  fireEvent.click(screen.getByText('Add Ingredient'))
  fireEvent.change(screen.getByPlaceholderText('Ingredient 1'), {
    target: { value: 'Carrot' },
  })
  fireEvent.click(screen.getByText('Save'))
  await waitFor(() => expect(createMock).toHaveBeenCalled())
  expect(createMock.mock.calls[0][0].ingredients[0].season_months).toEqual([
    1,
    2,
    3,
    4,
    5,
    6,
    7,
    8,
    9,
    10,
    11,
    12,
  ])
})
