import React, { useState } from 'react'
import { render, screen, cleanup } from '@testing-library/react'
import { test, expect, afterEach } from 'vitest'
import GroceryList from '../GroceryList'
import { AppContext } from '../../App'

function renderWithData(planData, recipeData) {
  function Wrapper({ children }) {
    const [plan, setPlan] = useState(planData)
    const [recipes, setRecipes] = useState(recipeData)
    const value = { plan, setPlan, recipes, setRecipes }
    return <AppContext.Provider value={value}>{children}</AppContext.Provider>
  }
  return render(
    <Wrapper>
      <GroceryList />
    </Wrapper>
  )
}

afterEach(() => {
  cleanup()
})

test('aggregates ingredients and skips leftovers', () => {
  const plan = {
    '2024-01-01': ['A'],
    '2024-01-02': ['A (leftover)', 'B'],
  }
  const recipes = [
    { title: 'A', ingredients: [{ name: 'Egg', quantity: 2, unit: 'pcs' }] },
    {
      title: 'B',
      ingredients: [
        { name: 'Egg', quantity: 1, unit: 'pcs' },
        { name: 'Flour', quantity: 100, unit: 'g' },
      ],
    },
  ]
  renderWithData(plan, recipes)
  expect(screen.getByText('Egg: 3 pcs')).toBeInTheDocument()
  expect(screen.getByText('Flour: 100 g')).toBeInTheDocument()
})
