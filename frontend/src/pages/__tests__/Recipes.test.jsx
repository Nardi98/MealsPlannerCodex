import React, { useState } from 'react'
import { render, screen, waitFor, cleanup } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { vi, afterEach, test, expect } from 'vitest'
import Recipes from '../Recipes'
import { AppContext } from '../../App'
import { tagsApi, recipesApi } from '../../api'

function renderWithContext() {
  function Wrapper({ children }) {
    const [recipes, setRecipes] = useState([])
    const value = { recipes, setRecipes, plan: {}, setPlan: () => {} }
    return (
      <AppContext.Provider value={value}>
        <MemoryRouter>{children}</MemoryRouter>
      </AppContext.Provider>
    )
  }
  return render(
    <Wrapper>
      <Recipes />
    </Wrapper>
  )
}

afterEach(() => {
  vi.restoreAllMocks()
  cleanup()
})

test('shows course next to recipe title', async () => {
  vi.spyOn(tagsApi, 'fetchAll').mockResolvedValue([])
  vi.spyOn(recipesApi, 'fetchAll').mockResolvedValue([
    { id: 1, title: 'Soup', course: 'main', tags: [], ingredients: [] },
  ])
  renderWithContext()
  await waitFor(() => screen.getByText('Soup'))
  expect(screen.getByText('[main]')).toBeInTheDocument()
})
