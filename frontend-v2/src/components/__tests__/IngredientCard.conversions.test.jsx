/** @vitest-environment jsdom */
import { render, screen, cleanup } from '@testing-library/react'
import { afterEach, expect, test } from 'vitest'
import '@testing-library/jest-dom/vitest'
import IngredientCard from '../IngredientCard'

afterEach(cleanup)

// The card makes the pantry's knowledge visible at a glance, and gives the
// shopping list's "combine" links somewhere coherent to land.
test('shows the measurements a piece weight makes reachable', () => {
  render(<IngredientCard name="Onion" grams_per_piece={150} expanded />)

  expect(screen.getByText('g')).toBeInTheDocument()
  expect(screen.getByText('piece')).toBeInTheDocument()
  expect(screen.queryByText('ml')).toBeNull()
})

test('shows all three when the ingredient is weighed, measured and counted', () => {
  render(
    <IngredientCard name="Butter" grams_per_ml={0.911} grams_per_piece={227} expanded />,
  )

  expect(screen.getByText('g')).toBeInTheDocument()
  expect(screen.getByText('ml')).toBeInTheDocument()
  expect(screen.getByText('piece')).toBeInTheDocument()
})

test('an ingredient with no conversions is a normal ingredient', () => {
  // No warning, no completeness meter, no "needs attention". Nothing to say.
  render(<IngredientCard name="Salt" expanded />)

  expect(screen.getByText('Salt')).toBeInTheDocument()
  expect(screen.queryByText('g')).toBeNull()
  expect(screen.queryByText(/missing|incomplete|attention/i)).toBeNull()
})
