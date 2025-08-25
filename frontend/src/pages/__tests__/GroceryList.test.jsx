import React from 'react'
import { render, screen } from '@testing-library/react'
import { test, expect } from 'vitest'
import GroceryList from '../GroceryList'
import { AppContext } from '../../App'

test('aggregates ingredients from plan', async () => {
  const plan = {
    '2024-06-01': ['Recipe A', 'Recipe B'],
    '2024-06-02': ['Recipe A (leftover)'],
  }
  const recipes = [
    {
      title: 'Recipe A',
      ingredients: [
        { name: 'Egg', quantity: 2 },
        { name: 'Milk', quantity: 1, unit: 'L' },
      ],
    },
    {
      title: 'Recipe B',
      ingredients: [
        { name: 'Egg', quantity: 1 },
        { name: 'Flour', quantity: 200, unit: 'g' },
      ],
    },
  ]
  render(
    <AppContext.Provider value={{ plan, recipes, setRecipes: () => {}, setPlan: () => {} }}>
      <GroceryList />
    </AppContext.Provider>
  )
  expect(await screen.findByText(/Egg 3/)).toBeInTheDocument()
  expect(screen.getByText(/Milk 1 L/)).toBeInTheDocument()
  expect(screen.getByText(/Flour 200 g/)).toBeInTheDocument()
})
