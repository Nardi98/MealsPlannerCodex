import React from 'react'
import { render, screen } from '@testing-library/react'
import { describe, test, expect } from 'vitest'
import GroceryList from '../GroceryList'
import { AppContext } from '../../App'

function renderWithContext(plan, recipes) {
  const value = { plan, recipes, setPlan: () => {}, setRecipes: () => {} }
  return render(
    <AppContext.Provider value={value}>
      <GroceryList />
    </AppContext.Provider>
  )
}

describe('GroceryList', () => {
  test('aggregates ingredients and ignores leftovers', () => {
    const plan = {
      '2024-01-01': [{ main: 'A', sides: ['B (leftover)'] }],
      '2024-01-02': [{ main: 'A', sides: ['B'] }],
    }
    const recipes = [
      {
        id: 1,
        title: 'A',
        ingredients: [
          { id: 1, name: 'Carrot', quantity: 1, unit: 'kg' },
          { id: 2, name: 'Onion', quantity: 2, unit: null },
        ],
      },
      {
        id: 2,
        title: 'B',
        ingredients: [{ id: 3, name: 'Carrot', quantity: 0.5, unit: 'kg' }],
      },
    ]
    renderWithContext(plan, recipes)
    expect(screen.getByText('Carrot: 2.5 kg')).toBeInTheDocument()
    expect(screen.getByText('Onion: 4')).toBeInTheDocument()
  })

  test('includes ingredients from side dishes', () => {
    const plan = {
      '2024-01-01': [{ main: 'A', sides: ['B'] }],
    }
    const recipes = [
      {
        id: 1,
        title: 'A',
        ingredients: [{ id: 1, name: 'Carrot', quantity: 1, unit: 'kg' }],
      },
      {
        id: 2,
        title: 'B',
        ingredients: [{ id: 2, name: 'Potato', quantity: 3, unit: null }],
      },
    ]
    renderWithContext(plan, recipes)
    expect(screen.getByText('Carrot: 1 kg')).toBeInTheDocument()
    expect(screen.getByText('Potato: 3')).toBeInTheDocument()
  })
})

