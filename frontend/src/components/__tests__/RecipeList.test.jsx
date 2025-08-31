import React from 'react'
import { render, screen, waitFor, cleanup } from '@testing-library/react'
import { vi, afterEach, test, expect } from 'vitest'
import RecipeList from '../RecipeList'
import { recipesApi } from '../../api'

afterEach(() => {
  vi.restoreAllMocks()
  cleanup()
})

test('displays course label', async () => {
  vi.spyOn(recipesApi, 'fetchAll').mockResolvedValue([
    { id: 1, title: 'Soup', course: 'main' },
  ])
  render(<RecipeList />)
  await waitFor(() => screen.getByText('Soup'))
  expect(screen.getByText('main')).toBeInTheDocument()
})
